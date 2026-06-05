# LiveKit Voice Agent (inbound + outbound, configurable prompt)

A single Python voice agent that handles **inbound** and **outbound** phone
calls (and web/app sessions), with a **configurable prompt** so the same code
can act as a customer-support agent, an HR screening agent, or anything else
you define.

It uses the current LiveKit Agents (v1.5) `AgentServer` API and a
**STT → LLM → TTS** pipeline running through **LiveKit Inference** (so you don't
need separate Deepgram/OpenAI/Cartesia API keys to start).

```
src/
  agent.py        One worker for inbound + outbound + web. Picks a profile per call.
  profiles.py     The configurable prompts (customer_support, hr_screening, ...).
scripts/
  setup_outbound_trunk.py   One-time: register your SIP provider for outbound.
  setup_inbound.py          One-time: route inbound calls to the agent.
  make_outbound_call.py     Trigger an outbound call.
.env.example      Copy to .env.local and fill in.
requirements.txt
```

---

## How it works (one minute)

Every call becomes a LiveKit **room**; the agent joins it as a participant.
A small bit of **JSON metadata** tells the worker what to do:

| Field          | Meaning                                                        |
| -------------- | -------------------------------------------------------------- |
| `profile`      | Which prompt to use (`customer_support`, `hr_screening`, ...). |
| `phone_number` | Present only for **outbound** — the number to dial.            |

- **Inbound:** a dispatch rule (from `setup_inbound.py` or the dashboard) sets
  `profile` and routes the caller in.
- **Outbound:** `make_outbound_call.py` sets `profile` + `phone_number`; the
  worker dials out via SIP.
- **Web:** a browser client joins a room; no metadata needed.

---

## Prerequisites

- Python ≥ 3.10
- A free [LiveKit Cloud](https://cloud.livekit.io/) project
- The [LiveKit CLI](https://docs.livekit.io/reference/developer-tools/livekit-cli/)
  (`lk`) — optional but handy
- **For outbound only:** an account with a SIP provider (Twilio, Telnyx,
  Plivo, or Wavix) and a phone number, since LiveKit Phone Numbers is
  inbound-only for now.

---

## Setup

```bash
# 1. Install dependencies (a virtual environment is recommended)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env.local
# edit .env.local: add LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET

# 3. Download the local model files (VAD + turn detector). One time only.
python -m livekit.agents download-files
```

### Test it locally first (no phone needed)

```bash
python services/agent.py console
```

This runs the agent in your terminal so you can talk to it and confirm the
pipeline and prompt work before wiring up telephony.

### Run it connected to LiveKit Cloud

```bash
python services/agent.py dev
```

Now it's reachable from the web Agent Console, inbound calls, and outbound
dispatches. Keep this running while you do the steps below.

---

## Inbound calls

1. **Get a number.**
   - *Easiest:* buy a **LiveKit Phone Number** in the Cloud dashboard
     (Telephony), or with `lk number ...`.
   - *Or* bring a third-party number by creating an **inbound trunk**
     (`lk sip inbound create`, or the dashboard).
2. **Route calls to the agent.** Run:
   ```bash
   python scripts/setup_inbound.py
   ```
   (Or configure the dispatch rule in the dashboard.) Edit `PROFILE` in that
   script to choose which prompt inbound callers get.
3. **Call your number.** With `python src/agent.py dev` running, dial in and the
   agent answers.

---

## Outbound calls

LiveKit Phone Numbers can't place outbound calls yet, so use a SIP provider.

1. **Register your provider's trunk** (one time). Fill in the constants at the
   top of `scripts/setup_outbound_trunk.py`, then:
   ```bash
   python scripts/setup_outbound_trunk.py
   ```
   Copy the printed trunk ID into `.env.local` as `SIP_OUTBOUND_TRUNK_ID`.
2. **Place a call** (with the worker running):
   ```bash
   python scripts/make_outbound_call.py +14155550100 hr_screening
   ```
   The agent dials the number and runs the HR screening prompt. Omit the profile
   to use `customer_support`.

> **Heads-up on outbound:** unsolicited outbound calling is regulated (TCPA in
> the US, GDPR in the EU, and more). Make sure you have consent and follow the
> rules for your region.

---

## Customizing the prompt

Open `src/profiles.py`. Each profile is a system prompt + an opening line +
a voice. Edit the existing ones or add a new `AgentProfile` to `PROFILES`, then
reference it by its `key` in the dispatch rule (inbound) or the dialer command
(outbound). Tips for voice prompts: keep replies short, one question at a time,
and no markdown or symbols (they get read aloud).

To swap models (e.g. use Claude as the LLM, or your own provider keys instead of
LiveKit Inference), change the `stt` / `llm` / `tts` lines in `src/agent.py`.
See https://docs.livekit.io/agents/models/ for the options.

---

## Honest notes

- This follows LiveKit's current documented patterns, but I couldn't run it
  against a live LiveKit project, real SIP trunks, or provider keys. Treat the
  first run as integration testing.
- The spots most likely to need a small tweak for your exact SDK build are the
  **SIP request field names** in `scripts/setup_outbound_trunk.py` and the
  **dispatch-rule object names** in `scripts/setup_inbound.py` — these have
  shifted across versions. If something doesn't match, check the current shapes
  with `lk docs search "outbound trunk"` / `lk docs search "dispatch rule"` or
  the SIP API reference: https://docs.livekit.io/reference/telephony/sip-api/
- Noise cancellation is loaded optionally; the agent runs without it.
```
