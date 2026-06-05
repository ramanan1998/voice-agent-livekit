
"""
Agent profiles = the configurable "personality + job" of the agent.

Each profile is just a system prompt + an opening line + a voice. The same
worker (agent.py) can run ANY of these; which one runs is chosen at dispatch
time via job metadata (see scripts/make_outbound_call.py and the inbound
dispatch rule). To add a new use case, add another AgentProfile to PROFILES.

Prompt-writing notes for voice (these matter a lot for how natural it sounds):
  - Keep replies short. Long paragraphs feel unnatural out loud.
  - No markdown, bullet points, emojis, or symbols. They get read aloud.
  - Write for the ear, not the eye.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    key: str
    # The system prompt that defines the agent's role and behavior.
    instructions: str
    # Instruction used to generate the first thing the agent says.
    greeting_instructions: str
    # Cartesia voice ID, used by the TTS model in MODE=cascade. Pick voices at
    # https://docs.livekit.io/agents/models/tts/ -> Cartesia.
    voice: str = "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
    # Named voice used in MODE=realtime (OpenAI Realtime). Options include
    # coral, alloy, echo, ash, ballad, sage, verse, shimmer.
    realtime_voice: str = "coral"


# ----------------------------------------------------------------------------
# Profile 1: Customer support
# ----------------------------------------------------------------------------
CUSTOMER_SUPPORT = AgentProfile(
    key="customer_support",
    instructions=(
        "Your name is Daisy. "
        "You are support assistant from Blackwins Tech Solutions, a company that makes Digital apps, AI services, and Cloud Hosting. "
        "You are a friendly customer support voice agent for the company. "
        "Your job is to understand the caller's problem, answer clearly, and "
        "resolve it or route it to the right place. "
        "Speak naturally and warmly, like a helpful human on the phone. "
        "Keep every response short, ideally one or two sentences. "
        "Ask one question at a time. Never read out symbols, bullet points, or "
        "formatting. Spell out numbers and steps in plain spoken language. "
        "If you do not know something or cannot help, say so honestly and offer "
        "to take a message or transfer the caller, rather than guessing. "
        "Confirm important details, like names, order numbers, or callback "
        "numbers, by repeating them back."
    ),
    greeting_instructions=(
        "Greet the caller warmly, say you are the support assistant, and ask "
        "how you can help today. Keep it to one short sentence."
    ),
    realtime_voice="coral",
)


# ----------------------------------------------------------------------------
# Profile 2: HR screening
# ----------------------------------------------------------------------------
HR_SCREENING = AgentProfile(
    key="hr_screening",
    instructions=(
        "You are an HR screening voice agent conducting a brief, friendly "
        "first-round phone screen with a job candidate. "
        "Your goal is to confirm basic fit and logistics, not to make a hiring "
        "decision. "
        "Cover these areas, one question at a time, in a natural conversational "
        "order: confirm the role they applied for, their current notice period "
        "or availability, their salary expectations, whether they are willing "
        "to work the required location or schedule, and one or two short "
        "questions about their most relevant experience. "
        "Speak warmly and professionally. Keep each turn short. "
        "Listen fully before moving on, and acknowledge their answers briefly. "
        "Do not make promises about outcomes, compensation, or timelines. "
        "If asked something you are not authorized to answer, say a member of "
        "the team will follow up. "
        "At the end, thank them, tell them the team will review and follow up "
        "by email, and say goodbye."
    ),
    greeting_instructions=(
        "Introduce yourself as the screening assistant calling about their "
        "application, confirm you have reached the right person, and ask if now "
        "is still a good time for a short call. Keep it to one or two sentences."
    ),
    realtime_voice="coral",
)


# Registry: dispatch metadata picks a profile by this key.
PROFILES: dict[str, AgentProfile] = {
    CUSTOMER_SUPPORT.key: CUSTOMER_SUPPORT,
    HR_SCREENING.key: HR_SCREENING,
}

# Used when dispatch metadata doesn't specify a profile.
DEFAULT_PROFILE_KEY = CUSTOMER_SUPPORT.key


def get_profile(key: str | None) -> AgentProfile:
    """Return the profile for `key`, falling back to the default."""
    if key and key in PROFILES:
        return PROFILES[key]
    return PROFILES[DEFAULT_PROFILE_KEY]