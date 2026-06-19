"""A small replay harness for asserting grounding behaviour in CI.

Turn "we hope it doesn't fabricate" into a test gate. Build a transcript, run a
guarded tool, and assert it was blocked (ungrounded) or that it committed.

Example::

    from saidso.testing import GroundingCase

    def test_invented_dob_is_blocked():
        (GroundingCase(register_patient)
            .user("Hi, I'd like an appointment")
            .call(name="John Doe", dob="1990-01-01")
            .assert_blocked("name", "dob"))
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .attestation import AttestationLog
from .context import call_context
from .result import SteerBack
from .transcript import Transcript

_NO_EXPECTED = object()  # sentinel: "no expected return supplied"


class GroundingCase:
    """Fluent builder for a single grounding replay assertion."""

    def __init__(
        self,
        tool,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        now: Optional[date] = None,
    ) -> None:
        self._tool = tool
        self._tr = Transcript()
        self._metadata = metadata or {}
        self._now = now
        self._log = AttestationLog()
        self._result: Any = None
        self._ran = False

    # -- build the conversation ------------------------------------------ #

    def user(self, text: str) -> "GroundingCase":
        self._tr.add_user(text)
        return self

    def agent(self, text: str) -> "GroundingCase":
        self._tr.add_agent(text)
        return self

    def caller_id(self, value: str) -> "GroundingCase":
        self._metadata["caller_id"] = value
        return self

    # -- invoke ---------------------------------------------------------- #

    def call(self, **kwargs) -> "GroundingCase":
        """Invoke the guarded tool with the built context (sync tools only)."""
        with call_context(
            self._tr, metadata=self._metadata, now=self._now,
            ledger=self._log, call_id="test",
        ):
            self._result = self._tool(**kwargs)
        self._ran = True
        return self

    # -- assertions ------------------------------------------------------ #

    @property
    def result(self) -> Any:
        self._require_ran()
        return self._result

    @property
    def blocked(self) -> bool:
        self._require_ran()
        return isinstance(self._result, SteerBack)

    @property
    def attestations(self) -> List[dict]:
        return self._log.export()

    def assert_blocked(self, *expected_args: str) -> "GroundingCase":
        self._require_ran()
        if not self.blocked:
            raise AssertionError(
                f"expected a block but tool committed: {self._result!r}"
            )
        if expected_args:
            failed = {f.name for f in self._result.failed}
            missing = set(expected_args) - failed
            if missing:
                raise AssertionError(
                    f"expected these args to be ungrounded {sorted(expected_args)}, "
                    f"but only {sorted(failed)} were blocked"
                )
        return self

    def assert_grounded(self, expected_return: Any = _NO_EXPECTED) -> "GroundingCase":
        self._require_ran()
        if self.blocked:
            raise AssertionError(
                f"expected the tool to commit but it was blocked: "
                f"{self._result.message!r}"
            )
        if expected_return is not _NO_EXPECTED and self._result != expected_return:
            raise AssertionError(
                f"expected return {expected_return!r}, got {self._result!r}"
            )
        return self

    def _require_ran(self) -> None:
        if not self._ran:
            raise RuntimeError("call(...) the tool before asserting")


def replay(tool, turns: List[Tuple[str, str]], call_kwargs: Dict[str, Any], **ctx_kwargs):
    """One-shot helper: build from ``(speaker, text)`` turns, call, return case."""
    case = GroundingCase(tool, **ctx_kwargs)
    for speaker, text in turns:
        (case.user if speaker == "user" else case.agent)(text)
    return case.call(**call_kwargs)
