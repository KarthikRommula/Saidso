"""The provenance ledger: proof that every committed argument was grounded."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

from .result import ArgFinding


@dataclass
class Attestation:
    """A receipt: this action ran, and here is what grounded every argument."""

    action: str
    ts: float
    call_id: Optional[str]
    args: List[ArgFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "ts": self.ts,
            "call_id": self.call_id,
            "args": [
                {
                    "arg": f.name,
                    "policy": f.result.policy,
                    "value": f.result.value,
                    "confidence": round(f.result.confidence, 4),
                    "span": f.result.span.to_dict() if f.result.span else None,
                }
                for f in self.args
            ],
        }


class AttestationLog:
    """Collects attestations in memory and (optionally) appends them as JSONL.

    Pass ``path=`` to persist an audit trail; otherwise records are kept in
    memory and reachable via :attr:`records`.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self._records: List[Attestation] = []
        self._lock = threading.Lock()

    def record(self, attestation: Attestation) -> Attestation:
        with self._lock:
            self._records.append(attestation)
            if self.path:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(attestation.to_dict()) + "\n")
        return attestation

    def build(self, action: str, findings: List[ArgFinding], call_id: Optional[str] = None) -> Attestation:
        return self.record(
            Attestation(action=action, ts=time.time(), call_id=call_id, args=list(findings))
        )

    @property
    def records(self) -> List[Attestation]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def export(self) -> List[dict]:
        return [a.to_dict() for a in self._records]
