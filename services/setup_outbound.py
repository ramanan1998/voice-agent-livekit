# """
# One-time setup: create an OUTBOUND SIP trunk.

# LiveKit Phone Numbers does not yet support outbound calling, so outbound goes
# through a third-party SIP provider (Twilio, Telnyx, Plivo, Wavix, etc.). This
# script registers that provider's trunk with LiveKit and prints the trunk ID.

# Put the printed ID into .env.local as SIP_OUTBOUND_TRUNK_ID.

# Fill in the four constants below from your SIP provider, then run:
#     uv run scripts/setup_outbound_trunk.py

# You can also do this with the LiveKit CLI (`lk sip outbound create`) or the
# LiveKit Cloud dashboard (Telephony -> Configuration -> Outbound) if you prefer.
# """

# from __future__ import annotations

# import asyncio

# from dotenv import load_dotenv

# from livekit import api

# load_dotenv(".env.local")

# # ---- Fill these in from your SIP provider ----------------------------------
# TRUNK_NAME = "My Outbound Trunk"
# # The phone number you'll call FROM, in E.164 format.
# CALLER_NUMBER = "+14155550100"
# # Your provider's SIP termination/trunk hostname (no scheme), e.g.
# # "my-trunk.pstn.twilio.com" for Twilio.
# SIP_ADDRESS = "your-trunk.pstn.provider.com"
# # Credentials your provider requires to authorize outbound calls.
# SIP_USERNAME = "your_sip_username"
# SIP_PASSWORD = "your_sip_password"
# # ----------------------------------------------------------------------------


# async def main() -> None:
#     lkapi = api.LiveKitAPI()
#     try:
#         trunk = api.SIPOutboundTrunkInfo(
#             name=TRUNK_NAME,
#             address=SIP_ADDRESS,
#             numbers=[CALLER_NUMBER],
#             auth_username=SIP_USERNAME,
#             auth_password=SIP_PASSWORD,
#         )
#         resp = await lkapi.sip.create_sip_outbound_trunk(
#             api.CreateSIPOutboundTrunkRequest(trunk=trunk)
#         )
#         print("Outbound trunk created.")
#         print(f"  Trunk ID: {resp.sip_trunk_id}")
#         print("Add this to .env.local:")
#         print(f"  SIP_OUTBOUND_TRUNK_ID={resp.sip_trunk_id}")
#     finally:
#         await lkapi.aclose()


# if __name__ == "__main__":
#     asyncio.run(main())



"""
One-time setup: create the LiveKit OUTBOUND trunk that dials through Vobiz.

This links your LiveKit project to your Vobiz SIP trunk. Run it once; it prints
a LiveKit trunk ID that you paste into .env.local as SIP_OUTBOUND_TRUNK_ID
(which agent.py reads when placing outbound calls).

Credentials come from the Vobiz console (SIP Trunk > Outbound Trunks):
    VOBIZ_SIP_DOMAIN      -> <your_unique_domain>.sip.vobiz.ai  (NOT plain sip.vobiz.ai)
    VOBIZ_USERNAME        -> trunk username
    VOBIZ_PASSWORD        -> trunk password
    VOBIZ_OUTBOUND_NUMBER -> your Vobiz number in E.164, used as caller ID

Run:
    uv run scripts/setup_outbound_trunk.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from livekit import api

load_dotenv(Path(__file__).resolve().parent.parent /".env.local")

TRUNK_NAME = "Vobiz Outbound"

VOBIZ_SIP_DOMAIN = os.getenv("VOBIZ_SIP_DOMAIN", "")
VOBIZ_USERNAME = os.getenv("VOBIZ_USERNAME", "")
VOBIZ_PASSWORD = os.getenv("VOBIZ_PASSWORD", "")
VOBIZ_OUTBOUND_NUMBER = os.getenv("VOBIZ_OUTBOUND_NUMBER", "")


def _print_env_line(trunk_id: str) -> None:
    print("\nAdd this to .env.local (agent.py reads SIP_OUTBOUND_TRUNK_ID):")
    print(f"  SIP_OUTBOUND_TRUNK_ID={trunk_id}\n")


async def main() -> None:
    missing = [
        name
        for name, val in {
            "VOBIZ_SIP_DOMAIN": VOBIZ_SIP_DOMAIN,
            "VOBIZ_USERNAME": VOBIZ_USERNAME,
            "VOBIZ_PASSWORD": VOBIZ_PASSWORD,
            "VOBIZ_OUTBOUND_NUMBER": VOBIZ_OUTBOUND_NUMBER,
        }.items()
        if not val
    ]
    if missing:
        raise SystemExit(f"Missing in .env.local: {', '.join(missing)}")

    lkapi = api.LiveKitAPI()
    try:
        # Idempotent: reuse a trunk with the same name instead of duplicating.
        existing = await lkapi.sip.list_sip_outbound_trunk(
            api.ListSIPOutboundTrunkRequest()
        )
        for t in existing.items:
            if t.name == TRUNK_NAME:
                print(f"Outbound trunk already exists: {t.sip_trunk_id}")
                _print_env_line(t.sip_trunk_id)
                return

        print(f"Creating outbound trunk -> {VOBIZ_SIP_DOMAIN}")
        trunk = await lkapi.sip.create_sip_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    name=TRUNK_NAME,
                    address=VOBIZ_SIP_DOMAIN,         # exact Vobiz domain
                    auth_username=VOBIZ_USERNAME,
                    auth_password=VOBIZ_PASSWORD,
                    numbers=[VOBIZ_OUTBOUND_NUMBER],  # caller ID presented
                    # If Vobiz tells you to force a transport, uncomment:
                    # transport=api.SIPTransport.SIP_TRANSPORT_UDP,
                )
            )
        )
        print(f"Created outbound trunk: {trunk.sip_trunk_id}")
        _print_env_line(trunk.sip_trunk_id)
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    asyncio.run(main())