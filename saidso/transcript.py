"""The rolling, timestamped transcript the firewall checks values against."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional

USER = "user"
AGENT = "agent"
SYSTEM = "system"


@dataclass
class Turn:
    """A single spoken (or system) turn in the conversation."""

    speaker: str
    text: str
    ts: float  # seconds (epoch or call-relative; the matcher only compares/labels)
    id: int

    def to_dict(self) -> dict:
        return {"id": self.id, "speaker": self.speaker, "ts": self.ts, "text": self.text}


class Transcript:
    """An append-only buffer of conversation turns.

    Feed it user/agent turns as the call progresses; the firewall reads from it
    to decide whether a tool argument is grounded in what was actually said.
    """

    def __init__(self, turns: Optional[Iterable[Turn]] = None) -> None:
        self._turns: List[Turn] = list(turns) if turns else []
        self._next_id = (max((t.id for t in self._turns), default=-1)) + 1

    # -- mutation -------------------------------------------------------- #

    def add(self, speaker: str, text: str, ts: Optional[float] = None) -> Turn:
        turn = Turn(
            speaker=speaker,
            text=text or "",
            ts=time.time() if ts is None else ts,
            id=self._next_id,
        )
        self._next_id += 1
        self._turns.append(turn)
        return turn

    def add_user(self, text: str, ts: Optional[float] = None) -> Turn:
        return self.add(USER, text, ts)

    def add_agent(self, text: str, ts: Optional[float] = None) -> Turn:
        return self.add(AGENT, text, ts)

    # -- access ---------------------------------------------------------- #

    def __iter__(self) -> Iterator[Turn]:
        return iter(self._turns)

    def __len__(self) -> int:
        return len(self._turns)

    @property
    def turns(self) -> List[Turn]:
        return list(self._turns)

    def user_turns(self) -> List[Turn]:
        return [t for t in self._turns if t.speaker == USER]

    def agent_turns(self) -> List[Turn]:
        return [t for t in self._turns if t.speaker == AGENT]

    def user_text(self) -> str:
        """All caller speech concatenated (for quick whole-transcript checks)."""
        return " ".join(t.text for t in self.user_turns())

    def turns_after(self, turn_id: int) -> List[Turn]:
        return [t for t in self._turns if t.id > turn_id]

    def to_list(self) -> List[dict]:
        return [t.to_dict() for t in self._turns]

    @classmethod
    def from_pairs(cls, pairs: Iterable[tuple]) -> "Transcript":
        """Build from ``(speaker, text)`` or ``(speaker, text, ts)`` tuples."""
        tr = cls()
        for p in pairs:
            if len(p) == 3:
                tr.add(p[0], p[1], p[2])
            else:
                tr.add(p[0], p[1])
        return tr
