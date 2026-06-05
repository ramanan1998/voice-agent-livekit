"""
The voice agent worker.

ONE worker handles every channel:
  - Inbound phone calls  (caller dials your number -> dispatch rule -> here)
  - Outbound phone calls  (you trigger a dispatch with a phone number -> here -> we dial out)
  - Web / app sessions    (a browser client joins the room -> here)

...and TWO pipeline modes, chosen by the MODE env var:
  - MODE=cascade   STT -> LLM -> TTS via LiveKit Inference. Keyless, great
                   transcripts/records, reliable tool-calling. Best for HR
                   screening. (Default.)
  - MODE=realtime  A single speech-to-speech model (OpenAI Realtime). Lower
                   latency, more natural prosody. Needs OPENAI_API_KEY. Great
                   for customer support rapport.

How it decides what to do
-------------------------
When dispatched into a room the agent receives optional JSON metadata (set by
the inbound dispatch rule, or by make_outbound_call.py for outbound):

    {
      "profile": "customer_support" | "hr_screening",
      "phone_number": "+14155550100"     # present only for OUTBOUND calls
    }

  - If "phone_number" is present, this is an OUTBOUND call: we connect to the
    room and place the call by creating a SIP participant.
  - If it's absent, the caller/user is already joining (inbound phone or web).

Run it:
    MODE=cascade  uv run src/agent.py console   # talk in your terminal
    MODE=realtime uv run src/agent.py dev        # connect to LiveKit Cloud
                  uv run src/agent.py start       # production
(MODE can also live in .env.local instead of being set inline.)
"""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    TurnHandlingOptions,
    inference,
    room_io,
)
from livekit.plugins.hume import TTS, VoiceById, VoiceProvider

from profiles import AgentProfile, get_profile

load_dotenv(".env.local")

logger = logging.getLogger("voice-agent")

# Must match the agent_name used in your dispatch rule and dialer script.
# Setting a name enables EXPLICIT dispatch (LiveKit's recommendation for
# telephony) so the agent only runs when you intend it to.
AGENT_NAME = "voice-agent"

# The outbound SIP trunk to dial through. Set this in .env.local after you
# create the trunk (scripts/setup_outbound_trunk.py).
OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID", "")

# Pipeline mode: "cascade" (default) or "realtime".
MODE = os.getenv("MODE", "cascade").strip().lower()

# ----------------------------------------------------------------------------
# IMPORTANT: LiveKit plugins register themselves at import time, and that MUST
# happen on the main thread (i.e. here at module load), never inside the job
# runner. So we import plugins at module level. We still import only what the
# selected MODE needs, by branching on MODE here at load time.
# ----------------------------------------------------------------------------
if MODE == "realtime":
    from livekit.plugins import openai  # speech-to-speech
else:
    from livekit.plugins import silero  # VAD
    from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Optional telephony noise cancellation (both modes). Guarded so a missing or
# renamed plugin doesn't stop the agent from running.
try:
    from livekit.plugins import noise_cancellation  # type: ignore
except Exception:  # noqa: BLE001 - optional enhancement
    noise_cancellation = None
    logger.info("Noise cancellation plugin not available; continuing without it.")


server = AgentServer()


# ----------------------------------------------------------------------------
# Pipeline builders. Plugins are already imported (above), so these just wire
# the components together.
# ----------------------------------------------------------------------------
def _build_cascade_session(profile: AgentProfile) -> AgentSession:
    """STT -> LLM -> TTS via LiveKit Inference (no provider keys needed)."""
    return AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        llm=inference.LLM(model="openai/gpt-5.2-chat-latest"),
        # tts=inference.TTS(model="cartesia/sonic-3", voice=profile.voice),
        tts=TTS(
            voice=VoiceById(
                id="f0ed2aeb-94c2-4d61-8cc4-e4af457f2d4c",
                provider=VoiceProvider.custom,
            ),
            instant_mode=True,
        ),
        # vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(turn_detection=MultilingualModel()),
    )


def _build_realtime_session(profile: AgentProfile) -> AgentSession:
    """Single speech-to-speech model. Requires OPENAI_API_KEY in the env.

    The realtime model handles STT, the LLM, TTS, and turn detection itself, so
    there's no separate VAD / turn detector here. It uses a named voice
    (profile.realtime_voice), not the Cartesia voice ID used by cascade.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "MODE=realtime requires OPENAI_API_KEY in .env.local. "
            "Either add it, or set MODE=cascade to use keyless LiveKit Inference."
        )
    return AgentSession(
        llm=openai.realtime.RealtimeModel(voice=profile.realtime_voice),
    )


def build_session(profile: AgentProfile) -> AgentSession:
    if MODE == "realtime":
        logger.info("Pipeline mode: realtime (speech-to-speech)")
        return _build_realtime_session(profile)
    if MODE != "cascade":
        logger.warning("Unknown MODE=%r; falling back to cascade.", MODE)
    logger.info("Pipeline mode: cascade (STT -> LLM -> TTS)")
    return _build_cascade_session(profile)


def _optional_room_options() -> "room_io.RoomOptions | None":
    """Telephony noise cancellation, if the plugin loaded. Applies to both modes."""
    if noise_cancellation is None:
        return None
    try:
        return room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        )
    except Exception:  # noqa: BLE001 - optional enhancement
        logger.info("Could not enable noise cancellation; continuing without it.")
        return None


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext):
    # ---- 1. Parse dispatch metadata ----------------------------------------
    metadata: dict = {}
    if ctx.job.metadata:
        try:
            metadata = json.loads(ctx.job.metadata)
        except json.JSONDecodeError:
            logger.warning("Could not parse job metadata: %r", ctx.job.metadata)

    profile = get_profile(metadata.get("profile"))
    phone_number = metadata.get("phone_number")  # only set for outbound
    logger.info(
        "Starting session: room=%s profile=%s mode=%s outbound=%s",
        ctx.room.name,
        profile.key,
        MODE,
        bool(phone_number),
    )

    # ---- 2. Connect to the room ---------------------------------------------
    await ctx.connect()

    # ---- 3. If outbound, place the call -------------------------------------
    if phone_number:
        if not OUTBOUND_TRUNK_ID:
            raise RuntimeError(
                "SIP_OUTBOUND_TRUNK_ID is not set. Create an outbound trunk "
                "(scripts/setup_outbound_trunk.py) and add its ID to .env.local."
            )
        await _dial_out(ctx, phone_number)

    # ---- 4. Build the pipeline (cascade or realtime) and start --------------
    session = build_session(profile)

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=profile.instructions),
        room_options=_optional_room_options(),
    )

    await session.generate_reply(instructions=profile.greeting_instructions)


async def _dial_out(ctx: agents.JobContext, phone_number: str) -> None:
    """Place an outbound PSTN call by adding a SIP participant to the room."""
    lkapi = api.LiveKitAPI()
    try:
        await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=OUTBOUND_TRUNK_ID,
                sip_call_to=phone_number,
                room_name=ctx.room.name,
                participant_identity="phone_user",
                participant_name="Phone User",
                krisp_enabled=True,
                # Block until the callee actually answers, so the agent doesn't
                # start talking into a ringing line or voicemail greeting.
                wait_until_answered=True,
            )
        )
        logger.info("Outbound call answered by %s", phone_number)
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    agents.cli.run_app(server)