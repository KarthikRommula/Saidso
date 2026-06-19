"""Return contracts: grounding verdicts, the steer-back message, attestations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Span:
    """A pointer into the transcript that grounds (or fails to ground) a value."""

    turn_id: int
    ts: float
    speaker: str
    text: str

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "ts": self.ts,
            "speaker": self.speaker,
            "text": self.text,
        }

    @classmethod
    def from_turn(cls, turn) -> "Span":
        return cls(turn_id=turn.id, ts=turn.ts, speaker=turn.speaker, text=turn.text)


@dataclass
class GroundingResult:
    """Verdict for a single argument against a single policy."""

    grounded: bool
    confidence: float
    policy: str
    value: Any
    reason: str = ""
    normalized: Any = None
    span: Optional[Span] = None

    def to_dict(self) -> dict:
        return {
            "grounded": self.grounded,
            "confidence": round(self.confidence, 4),
            "policy": self.policy,
            "value": self.value,
            "normalized": self.normalized,
            "reason": self.reason,
            "span": self.span.to_dict() if self.span else None,
        }


@dataclass
class ArgFinding:
    """A per-argument finding attached to an action's outcome."""

    name: str
    result: GroundingResult

    def to_dict(self) -> dict:
        return {"arg": self.name, **self.result.to_dict()}


# Human-friendly re-ask phrasing for common argument names.
_REASK_PHRASES = {
    "name": "your name",
    "full_name": "your full name",
    "dob": "your date of birth",
    "date_of_birth": "your date of birth",
    "birthday": "your date of birth",
    "phone": "your phone number",
    "email": "your email address",
    "address": "your address",
    "amount": "the amount",
    "account": "which account",
    "visit_date": "the date you'd like to come in",
    "appointment_date": "the appointment date",
    "consent": "your confirmation",
}


def _phrase_for(arg: str) -> str:
    return _REASK_PHRASES.get(arg, arg.replace("_", " "))


@dataclass
class SteerBack:
    """Returned instead of running the action when grounding fails.

    This is *not* a dead error. Hand ``message`` back to the agent as the tool
    result and it will re-ask the caller in-conversation, then try again.
    """

    action: str
    blocked: bool = True
    failed: List[ArgFinding] = field(default_factory=list)
    grounded: List[ArgFinding] = field(default_factory=list)
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            self.message = self._build_message()

    def _build_message(self) -> str:
        phrases = [_phrase_for(f.name) for f in self.failed]
        if not phrases:
            return f"Could not run {self.action}: an argument was not grounded."
        if len(phrases) == 1:
            ask = phrases[0]
        elif len(phrases) == 2:
            ask = f"{phrases[0]} and {phrases[1]}"
        else:
            ask = ", ".join(phrases[:-1]) + f", and {phrases[-1]}"
        return (
            f"I don't have {ask} from what the caller said. "
            f"Ask the caller for {ask}, then try again. "
            f"Do not guess or fill in placeholder values."
        )

    # -- adapters -------------------------------------------------------- #

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "blocked": self.blocked,
            "message": self.message,
            "failed": [f.to_dict() for f in self.failed],
            "grounded": [f.to_dict() for f in self.grounded],
        }

    def to_tool_message(self) -> str:
        """String to return as the tool-call result so the agent self-corrects."""
        return self.message

    def __bool__(self) -> bool:  # truthy-but-blocked guard for callers
        return False
