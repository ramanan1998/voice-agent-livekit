"""
One-time setup: create an INBOUND dispatch rule.

A dispatch rule decides what happens when someone calls your number. This rule
puts each caller in their own room and dispatches the agent with the
"customer_support" profile.

Works for both paths:
  - LiveKit Phone Numbers: you can also configure this in the Cloud dashboard
    (Telephony) instead of running this script.
  - Third-party SIP provider: first create an inbound trunk (CLI:
    `lk sip inbound create`, or the dashboard), then this rule routes its calls.

Run:
    uv run scripts/setup_inbound.py

To screen inbound callers with the HR profile instead, change PROFILE below,
or create a second rule on a different trunk/number.
"""

from __future__ import annotations

import asyncio
import json

from dotenv import load_dotenv

from livekit import api

load_dotenv(".env.local")

AGENT_NAME = "voice-agent"  # must match agent.py
PROFILE = "customer_support"  # which profile inbound callers get

# Optional: restrict this rule to specific inbound trunk IDs. Leave empty to
# apply to all inbound trunks on the project.
TRUNK_IDS: list[str] = []


async def main() -> None:
    lkapi = api.LiveKitAPI()
    try:
        request = api.CreateSIPDispatchRuleRequest(
            name="inbound-to-agent",
            trunk_ids=TRUNK_IDS,
            # Give every caller their own room (prefixed "call-").
            rule=api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix="call-",
                ),
            ),
            # Dispatch our named agent into that room, with the profile.
            room_config=api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=AGENT_NAME,
                        metadata=json.dumps({"profile": PROFILE}),
                    )
                ],
            ),
        )
        resp = await lkapi.sip.create_sip_dispatch_rule(request)
        print("Inbound dispatch rule created.")
        print(f"  Dispatch rule ID: {resp.sip_dispatch_rule_id}")
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    asyncio.run(main())
