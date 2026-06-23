from datetime import datetime
from typing import Dict, List

from .message_bus import Message


class TraceCollector:
    """
    Collecteur de trace pour visualiser le dialogue entre agents.
    Enregistre chaque message échangé avec son horodatage,
    son expéditeur, son destinataire et son contenu.
    Utile pour la démonstration et le débogage.
    """

    def __init__(self):
        self._entries: List[dict] = []

    def record(self, message: Message, direction: str = "send") -> None:
        self._entries.append({
            "timestamp": message.timestamp.isoformat(),
            "direction": direction,
            "from": message.sender,
            "to": message.recipient or "(broadcast)",
            "type": message.type.value,
            "correlation_id": message.correlation_id,
            "trace_id": message.trace_id,
            "payload_summary": self._summarize(message.payload),
        })

    def record_batch(self, messages: List[Message], direction: str = "send") -> None:
        for msg in messages:
            self.record(msg, direction)

    def _summarize(self, payload: dict) -> str:
        keys = list(payload.keys())
        return f"{{{', '.join(keys)}}}"

    def get_trace(self) -> List[dict]:
        return list(self._entries)

    def get_formatted_trace(self) -> str:
        lines = ["┌─────────────────────────────────────────────────────────────"]
        lines.append("│ TRACE DE COLLABORATION DES AGENTS")
        lines.append("├─────────────────────────────────────────────────────────────")
        for i, entry in enumerate(self._entries):
            arrow = "→" if entry["direction"] == "send" else "←"
            lines.append(
                f"│ [{entry['timestamp'][11:19]}] {entry['from']} {arrow} {entry['to']}  "
                f"({entry['type']})"
            )
        lines.append("└─────────────────────────────────────────────────────────────")
        return "\n".join(lines)

    def summary(self) -> dict:
        exchanges = {}
        for e in self._entries:
            key = f"{e['from']} → {e['to']}"
            exchanges.setdefault(key, 0)
            exchanges[key] += 1
        return {
            "total_messages": len(self._entries),
            "exchanges": exchanges,
            "agents_impliques": list(set(
                e["from"] for e in self._entries
            ) | set(e["to"] for e in self._entries if e["to"] != "(broadcast)")),
        }

    def clear(self) -> None:
        self._entries.clear()
