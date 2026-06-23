from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentMessage:
    """Message passed between agents."""

    sender: str
    recipient: str
    msg_type: str  # "request" | "response" | "notification"
    payload: dict
    context: dict = field(default_factory=dict)
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    in_reply_to: str | None = None


class BaseAgent:
    """Base class for all agents."""

    def __init__(self, name: str):
        self.name = name
        self._mailbox: list[AgentMessage] = []

    def send(self, message: AgentMessage) -> AgentMessage:
        self._mailbox.append(message)
        return message

    def process(self, message: AgentMessage) -> AgentMessage:
        raise NotImplementedError

    def reply(self, request: AgentMessage, payload: dict, context: dict | None = None) -> AgentMessage:
        return AgentMessage(
            sender=self.name,
            recipient=request.sender,
            msg_type="response",
            payload=payload,
            context=context or request.context,
            in_reply_to=request.msg_id,
        )
