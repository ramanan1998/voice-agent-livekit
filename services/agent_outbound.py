# """
# Trigger an OUTBOUND call.

# This creates a uniquely-named room and dispatches the agent into it with the
# phone number to dial and the profile to use. The agent worker (agent.py) then
# places the call via SIP.

# Usage:
#     uv run scripts/make_outbound_call.py +14155550100 hr_screening
#     uv run scripts/make_outbound_call.py +14155550100        # defaults to customer_support

# Requires (in .env.local):
#     LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
# And the worker must be running (uv run src/agent.py dev) with
# SIP_OUTBOUND_TRUNK_ID configured.
# """

# from __future__ import annotations

# import argparse
# import asyncio
# import json
# import uuid

# from dotenv import load_dotenv

# from livekit import api

# load_dotenv(".env.local")

# AGENT_NAME = "voice-agent"  # must match agent.py


# async def main() -> None:
#     parser = argparse.ArgumentParser(description="Place an outbound call.")
#     parser.add_argument("phone_number", help="E.164 number to call, e.g. +14155550100")
#     parser.add_argument(
#         "profile",
#         nargs="?",
#         default="customer_support",
#         help="Agent profile key (customer_support | hr_screening).",
#     )
#     args = parser.parse_args()

#     room_name = f"outbound-{uuid.uuid4().hex[:8]}"
#     metadata = json.dumps(
#         {"phone_number": args.phone_number, "profile": args.profile}
#     )

#     lkapi = api.LiveKitAPI()
#     try:
#         dispatch = await lkapi.agent_dispatch.create_dispatch(
#             api.CreateAgentDispatchRequest(
#                 agent_name=AGENT_NAME,
#                 room=room_name,
#                 metadata=metadata,
#             )
#         )
#         print(f"Dispatched agent to room '{room_name}' to call {args.phone_number}")
#         print(f"Dispatch ID: {dispatch.id}")
#     finally:
#         await lkapi.aclose()


# if __name__ == "__main__":
#     asyncio.run(main())


"""
Trigger an OUTBOUND call.

This script does NOT dial anything itself. It dispatches the running agent
worker into a fresh room with the phone number in the job metadata. agent.py's
entrypoint sees "phone_number" and places the call through the Vobiz outbound
trunk (its _dial_out).

The worker must already be running in another shell:
    MODE=cascade uv run src/agent.py start

Then:
    uv run make_outbound_call.py +919876543210
    uv run make_outbound_call.py +919876543210 hr_screening
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

from livekit import api

load_dotenv(Path(__file__).resolve().parent.parent /".env.local")

AGENT_NAME = "voice-agent"          # must match agent.py
DEFAULT_PROFILE = "customer_support"


async def make_call(phone_number: str, profile: str) -> None:
    room_name = f"outbound-{uuid.uuid4().hex[:8]}"
    lkapi = api.LiveKitAPI()
    try:
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=json.dumps(
                    {"profile": profile, "phone_number": phone_number}
                ),
            )
        )
        print(f"Dispatched '{AGENT_NAME}' into room '{room_name}'")
        print(f"  Calling: {phone_number}  (profile: {profile})")
        print(f"  Dispatch ID: {getattr(dispatch, 'id', '(created)')}")
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: uv run make_outbound_call.py <+E164_number> [profile]\n"
            "  e.g. uv run make_outbound_call.py +919876543210 customer_support"
        )
    number = sys.argv[1]
    prof = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROFILE
    asyncio.run(make_call(number, prof))