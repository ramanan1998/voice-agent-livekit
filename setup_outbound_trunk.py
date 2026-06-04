"""
One-time setup: create an OUTBOUND SIP trunk.

LiveKit Phone Numbers does not yet support outbound calling, so outbound goes
through a third-party SIP provider (Twilio, Telnyx, Plivo, Wavix, etc.). This
script registers that provider's trunk with LiveKit and prints the trunk ID.

Put the printed ID into .env.local as SIP_OUTBOUND_TRUNK_ID.

Fill in the four constants below from your SIP provider, then run:
    uv run scripts/setup_outbound_trunk.py

You can also do this with the LiveKit CLI (`lk sip outbound create`) or the
LiveKit Cloud dashboard (Telephony -> Configuration -> Outbound) if you prefer.
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from livekit import api

load_dotenv(".env.local")

# ---- Fill these in from your SIP provider ----------------------------------
TRUNK_NAME = "My Outbound Trunk"
# The phone number you'll call FROM, in E.164 format.
CALLER_NUMBER = "+14155550100"
# Your provider's SIP termination/trunk hostname (no scheme), e.g.
# "my-trunk.pstn.twilio.com" for Twilio.
SIP_ADDRESS = "your-trunk.pstn.provider.com"
# Credentials your provider requires to authorize outbound calls.
SIP_USERNAME = "your_sip_username"
SIP_PASSWORD = "your_sip_password"
# ----------------------------------------------------------------------------


async def main() -> None:
    lkapi = api.LiveKitAPI()
    try:
        trunk = api.SIPOutboundTrunkInfo(
            name=TRUNK_NAME,
            address=SIP_ADDRESS,
            numbers=[CALLER_NUMBER],
            auth_username=SIP_USERNAME,
            auth_password=SIP_PASSWORD,
        )
        resp = await lkapi.sip.create_sip_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(trunk=trunk)
        )
        print("Outbound trunk created.")
        print(f"  Trunk ID: {resp.sip_trunk_id}")
        print("Add this to .env.local:")
        print(f"  SIP_OUTBOUND_TRUNK_ID={resp.sip_trunk_id}")
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    asyncio.run(main())
