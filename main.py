"""
FastAPI backend — step 1.

A basic API over the agents database:
  GET    /healthz          is the server up?
  GET    /agents           list all agents
  POST   /agents           create an agent
  GET    /agents/{id}      get one agent
  PUT    /agents/{id}      update an agent
  DELETE /agents/{id}      delete an agent

Run it:
    uvicorn main:app --reload --port 8000

Then open http://localhost:8000/docs for an interactive UI to try every endpoint.
"""

from __future__ import annotations
import os
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from db import get_session, init_db
from models import Agent, AgentCreate, AgentUpdate
from livekit import api
from dotenv import load_dotenv
 
load_dotenv(".env.local")
 
 
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
# When set, the token requests that LiveKit dispatch this named agent into the
# room as soon as the participant joins. Leave unset if your agent worker uses
# automatic dispatch instead.
LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "")
 
# How long an issued token stays valid. Joining must happen within this window;
# the session itself can outlast it.
TOKEN_TTL = timedelta(minutes=15)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup
    yield


app = FastAPI(title="Voice Agent Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _require_config() -> None:
    missing = [
        name
        for name, val in (
            ("LIVEKIT_URL", LIVEKIT_URL),
            ("LIVEKIT_API_KEY", LIVEKIT_API_KEY),
            ("LIVEKIT_API_SECRET", LIVEKIT_API_SECRET),
        )
        if not val
    ]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Server missing required env vars: {', '.join(missing)}",
        )
 
 
def _build_token(identity: str, name: str, room: str) -> str:
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=True,        # publish the user's microphone
        can_subscribe=True,      # hear the agent
        can_publish_data=True,   # send the end_call / control messages
    )
 
    builder = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(grants)
        .with_ttl(TOKEN_TTL)
    )
 
    # Optional explicit agent dispatch.
    if LIVEKIT_AGENT_NAME:
        builder = builder.with_room_config(
            api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(agent_name=LIVEKIT_AGENT_NAME)],
            )
        )
 
    return builder.to_jwt()
 
 
@app.get("/token")
def get_token(
    room: str | None = Query(default=None, description="Room to join; random if omitted"),
    identity: str | None = Query(default=None, description="Participant identity; random if omitted"),
    name: str | None = Query(default=None, description="Display name"),
):
    """Mint a join token. Called by the React client on 'Connect'."""
    _require_config()
 
    room_name = room or f"support-{uuid.uuid4().hex[:8]}"
    user_identity = identity or f"user-{uuid.uuid4().hex[:8]}"
    display_name = name or "Caller"
 
    jwt = _build_token(user_identity, display_name, room_name)
 
    return {
        "url": LIVEKIT_URL,
        "token": jwt,
        "room": room_name,
    }
 


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/agents")
def list_agents(session: Session = Depends(get_session)):
    return session.exec(select(Agent).order_by(Agent.id.desc())).all()


@app.post("/agents", status_code=201)
def create_agent(body: AgentCreate, session: Session = Depends(get_session)):
    agent = Agent(**body.model_dump(exclude_none=True))
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@app.get("/agents/{agent_id}")
def get_agent(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.put("/agents/{agent_id}")
def update_agent(
    agent_id: int, body: AgentUpdate, session: Session = Depends(get_session)
):
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    for field, value in updates.items():
        setattr(agent, field, value)
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    session.delete(agent)
    session.commit()
    return {"deleted": agent_id}

if __name__ == "__main__":
    import uvicorn
 
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=bool(os.getenv("RELOAD")),
    )