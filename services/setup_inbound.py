# """
# One-time setup: create an INBOUND dispatch rule.

# A dispatch rule decides what happens when someone calls your number. This rule
# puts each caller in their own room and dispatches the agent with the
# "customer_support" profile.

# Works for both paths:
#   - LiveKit Phone Numbers: you can also configure this in the Cloud dashboard
#     (Telephony) instead of running this script.
#   - Third-party SIP provider: first create an inbound trunk (CLI:
#     `lk sip inbound create`, or the dashboard), then this rule routes its calls.

# Run:
#     uv run scripts/setup_inbound.py

# To screen inbound callers with the HR profile instead, change PROFILE below,
# or create a second rule on a different trunk/number.
# """

# from __future__ import annotations

# import asyncio
# import json

# from dotenv import load_dotenv

# from livekit import api

# load_dotenv(".env.local")

# AGENT_NAME = "voice-agent"  # must match agent.py
# PROFILE = "customer_support"  # which profile inbound callers get

# # Optional: restrict this rule to specific inbound trunk IDs. Leave empty to
# # apply to all inbound trunks on the project.
# TRUNK_IDS: list[str] = []


# async def main() -> None:
#     lkapi = api.LiveKitAPI()
#     try:
#         request = api.CreateSIPDispatchRuleRequest(
#             name="inbound-to-agent",
#             trunk_ids=TRUNK_IDS,
#             # Give every caller their own room (prefixed "call-").
#             rule=api.SIPDispatchRule(
#                 dispatch_rule_individual=api.SIPDispatchRuleIndividual(
#                     room_prefix="call-",
#                 ),
#             ),
#             # Dispatch our named agent into that room, with the profile.
#             room_config=api.RoomConfiguration(
#                 agents=[
#                     api.RoomAgentDispatch(
#                         agent_name=AGENT_NAME,
#                         metadata=json.dumps({"profile": PROFILE}),
#                     )
#                 ],
#             ),
#         )
#         resp = await lkapi.sip.create_sip_dispatch_rule(request)
#         print("Inbound dispatch rule created.")
#         print(f"  Dispatch rule ID: {resp.sip_dispatch_rule_id}")
#     finally:
#         await lkapi.aclose()


# if __name__ == "__main__":
#     asyncio.run(main())




"""
One-time setup: LiveKit INBOUND for Vobiz.

Creates (idempotently) two things on the LiveKit side:
  1. an INBOUND trunk bound to your Vobiz number, and
  2. a DISPATCH RULE that puts each caller in their own "call-" room and
     dispatches agent.py with the customer_support profile.

It does NOT touch Vobiz. You still have to point your Vobiz trunk's inbound
destination at your LiveKit SIP URI (see the printed instructions at the end).

Env (.env.local):
    LIVEKIT_URL           wss://<project>.livekit.cloud   (used to guess SIP URI)
    VOBIZ_INBOUND_NUMBER  the Vobiz DID, E.164. Falls back to VOBIZ_OUTBOUND_NUMBER.

Run:
    uv run scripts/setup_inbound_trunk.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from livekit import api

load_dotenv(Path(__file__).resolve().parent.parent /".env.local")

AGENT_NAME = "voice-agent"        # must match agent.py
PROFILE = "customer_support"      # profile inbound callers get
TRUNK_NAME = "Vobiz Inbound"
RULE_NAME = "inbound-to-agent"

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
# Inbound number; default to the outbound number if a separate one isn't set.
INBOUND_NUMBER = os.getenv("VOBIZ_INBOUND_NUMBER") or os.getenv("VOBIZ_OUTBOUND_NUMBER", "")


def _sip_uri() -> str:
    """Best-guess LiveKit Cloud SIP URI from LIVEKIT_URL. Confirm against the
    dashboard (Settings > Project > SIP URI), which is authoritative."""
    project = LIVEKIT_URL.replace("wss://", "").replace("ws://", "").split(".")[0]
    return f"{project}.sip.livekit.cloud" if project else "<see dashboard>"


async def _get_or_create_trunk(lkapi: api.LiveKitAPI) -> str:
    trunks = await lkapi.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
    for t in trunks.items:
        if t.numbers and INBOUND_NUMBER in t.numbers:
            print(f"Inbound trunk already exists for {INBOUND_NUMBER}: {t.sip_trunk_id}")
            return t.sip_trunk_id

    print(f"Creating inbound trunk for {INBOUND_NUMBER}...")
    trunk = await lkapi.sip.create_sip_inbound_trunk(
        api.CreateSIPInboundTrunkRequest(
            trunk=api.SIPInboundTrunkInfo(
                name=TRUNK_NAME,
                numbers=[INBOUND_NUMBER],
                allowed_addresses=["0.0.0.0/0"],  # restrict to Vobiz IPs in prod
                krisp_enabled=True,
            )
        )
    )
    print(f"    Trunk: {trunk.sip_trunk_id}")
    return trunk.sip_trunk_id


async def _get_or_create_rule(lkapi: api.LiveKitAPI, trunk_id: str) -> str:
    rules = await lkapi.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
    for r in rules.items:
        if r.name == RULE_NAME:
            print(f"Dispatch rule already exists: {r.sip_dispatch_rule_id}")
            return r.sip_dispatch_rule_id

    print(f"Creating dispatch rule -> agent '{AGENT_NAME}' (profile '{PROFILE}')...")
    resp = await lkapi.sip.create_sip_dispatch_rule(
        api.CreateSIPDispatchRuleRequest(
            dispatch_rule=api.SIPDispatchRuleInfo(
                name=RULE_NAME,
                trunk_ids=[trunk_id],  # scope to the Vobiz inbound trunk
                rule=api.SIPDispatchRule(
                    dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                        room_prefix="call-",
                    ),
                ),
                room_config=api.RoomConfiguration(
                    agents=[
                        api.RoomAgentDispatch(
                            agent_name=AGENT_NAME,
                            metadata=json.dumps({"profile": PROFILE}),
                        )
                    ],
                ),
            )
        )
    )
    print(f"    Dispatch rule: {resp.sip_dispatch_rule_id}")
    return resp.sip_dispatch_rule_id


async def main() -> None:
    if not INBOUND_NUMBER:
        raise SystemExit(
            "Set VOBIZ_INBOUND_NUMBER (or VOBIZ_OUTBOUND_NUMBER) in .env.local."
        )

    lkapi = api.LiveKitAPI()
    try:
        trunk_id = await _get_or_create_trunk(lkapi)
        rule_id = await _get_or_create_rule(lkapi, trunk_id)

        print("\n" + "=" * 60)
        print("LiveKit side done.")
        print("=" * 60)
        print(f"  Trunk:  {trunk_id}  ({INBOUND_NUMBER})")
        print(f"  Rule:   {rule_id}  -> {AGENT_NAME} / {PROFILE}")
        print("\n  >>> Now, in the Vobiz console, set this number's inbound")
        print("  >>> destination to your LiveKit SIP URI (NO 'sip:' prefix):")
        print(f"  >>>     {_sip_uri()}")
        print("  >>> Confirm the exact URI in LiveKit: Settings > Project > SIP URI.")
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    asyncio.run(main())
