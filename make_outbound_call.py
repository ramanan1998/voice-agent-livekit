"""
Trigger an OUTBOUND call.

This creates a uniquely-named room and dispatches the agent into it with the
phone number to dial and the profile to use. The agent worker (agent.py) then
places the call via SIP.

Usage:
    uv run scripts/make_outbound_call.py +14155550100 hr_screening
    uv run scripts/make_outbound_call.py +14155550100        # defaults to customer_support

Requires (in .env.local):
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
And the worker must be running (uv run src/agent.py dev) with
SIP_OUTBOUND_TRUNK_ID configured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from dotenv import load_dotenv

from livekit import api

load_dotenv(".env.local")

AGENT_NAME = "voice-agent"  # must match agent.py


async def main() -> None:
    parser = argparse.ArgumentParser(description="Place an outbound call.")
    parser.add_argument("phone_number", help="E.164 number to call, e.g. +14155550100")
    parser.add_argument(
        "profile",
        nargs="?",
        default="customer_support",
        help="Agent profile key (customer_support | hr_screening).",
    )
    args = parser.parse_args()

    room_name = f"outbound-{uuid.uuid4().hex[:8]}"
    metadata = json.dumps(
        {"phone_number": args.phone_number, "profile": args.profile}
    )

    lkapi = api.LiveKitAPI()
    try:
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata,
            )
        )
        print(f"Dispatched agent to room '{room_name}' to call {args.phone_number}")
        print(f"Dispatch ID: {dispatch.id}")
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    asyncio.run(main())
