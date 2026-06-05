"""
Data models.

`Agent` is the database table. `AgentCreate` / `AgentUpdate` are the shapes the
API accepts as input (so clients can't set id or created_at directly).

The fields here describe a voice agent. We'll use them when we wire in the agent
worker in the next step, but for now they're just stored and served.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Agent(SQLModel, table=True):
    """A voice agent definition (one row per agent)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    call_type: str = "inbound"  # "inbound" | "outbound"
    use_case: str = ""
    description: str = ""

    # The prompts the agent will eventually use.
    instructions: str = ""
    greeting: str = ""

    # Pipeline + voice (used once the worker is connected).
    mode: str = "cascade"  # "cascade" | "realtime"
    voice: str = "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"

    created_at: datetime = Field(default_factory=_now)


class AgentCreate(SQLModel):
    name: str
    call_type: str = "inbound"
    use_case: str = ""
    description: str = ""
    instructions: str = ""
    greeting: str = ""
    mode: str = "cascade"
    voice: Optional[str] = None


class AgentUpdate(SQLModel):
    name: Optional[str] = None
    call_type: Optional[str] = None
    use_case: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    greeting: Optional[str] = None
    mode: Optional[str] = None
    voice: Optional[str] = None