from abc import ABC, abstractmethod
from typing import List, Optional

from .message_bus import Message, MessageBus, MessageType


class BaseAgent(ABC):
    """
    Agent de base pour le système multi-agent de détection d'anomalies.
    Chaque agent a un nom, une description de son rôle, et implémente
    la méthode handle_message() pour traiter les messages reçus.
    """

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.bus: Optional[MessageBus] = None

    @abstractmethod
    def handle_message(self, message: Message) -> List[Message]:
        ...

    def send_log(self, level: str, message: str) -> None:
        if self.bus:
            self.bus.send(Message(
                type=MessageType.LOG,
                payload={"level": level, "message": message, "agent": self.name},
                sender=self.name,
            ))

    def describe(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "type": self.__class__.__name__,
        }
