from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, List, Optional
import uuid


class MessageType(Enum):
    """Types de messages échangés entre agents du système multi-agent."""
    DETECTION_REQUEST = "detection_request"
    ANALYSE_PRIX = "analyse_prix"
    ANALYSE_DELAI = "analyse_delai"
    ANALYSE_DISPERSION = "analyse_dispersion"
    ANALYSE_ROTATION = "analyse_rotation"
    RESULTAT_ANOMALIE = "resultat_anomalie"
    RAPPORT_FINAL = "rapport_final"
    ERREUR = "erreur"
    LOG = "log"


@dataclass
class Message:
    """Message standardisé pour la communication entre agents."""
    type: MessageType
    payload: dict
    sender: str
    recipient: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def reply(self, msg_type: MessageType, payload: dict, sender: str) -> "Message":
        return Message(
            type=msg_type,
            payload=payload,
            sender=sender,
            recipient=self.sender,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
        )


class MessageBus:
    """
    Bus de messages asynchrone en mémoire.
    Permet aux agents de s'enregistrer, s'abonner à des types de messages,
    et d'échanger des messages de façon asynchrone.
    """

    def __init__(self):
        self._agents: dict[str, "BaseAgent"] = {}
        self._subscriptions: dict[MessageType, List[str]] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, agent: "BaseAgent") -> None:
        self._agents[agent.name] = agent
        agent.bus = self

    def subscribe(self, agent_name: str, msg_type: MessageType) -> None:
        if msg_type not in self._subscriptions:
            self._subscriptions[msg_type] = []
        if agent_name not in self._subscriptions[msg_type]:
            self._subscriptions[msg_type].append(agent_name)

    def send(self, message: Message) -> List[Message]:
        responses: List[Message] = []
        if message.recipient:
            agent = self._agents.get(message.recipient)
            if agent:
                responses.extend(agent.handle_message(message))
        else:
            subscribers = self._subscriptions.get(message.type, [])
            for name in subscribers:
                agent = self._agents.get(name)
                if agent and agent.name != message.sender:
                    responses.extend(agent.handle_message(message))
        return responses

    def get_agent(self, name: str) -> Optional["BaseAgent"]:
        return self._agents.get(name)

    @property
    def agents(self) -> dict:
        return dict(self._agents)
