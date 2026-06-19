"""The grounding policies: what makes an argument legitimate."""

from __future__ import annotations

from enum import Enum


class Policy(str, Enum):
    """Per-argument grounding rules.

    - ``SPOKEN``    : the value must appear in the caller's speech
                      (digits/dates/names normalized, fuzzy-matched).
    - ``CONFIRMED`` : the agent read the value back AND the caller affirmed it.
    - ``CALLER_ID`` : the value comes from trusted call metadata, not the mouth.
    - ``INFERABLE`` : the value is derivable from context (e.g. "tomorrow" + clock)
                      or was spoken explicitly.
    """

    SPOKEN = "spoken"
    CONFIRMED = "confirmed"
    CALLER_ID = "caller_id"
    INFERABLE = "inferable"


# Default confidence thresholds per policy (override via GroundingConfig).
DEFAULT_THRESHOLDS = {
    Policy.SPOKEN: 0.82,
    Policy.CONFIRMED: 0.82,
    Policy.CALLER_ID: 0.99,
    Policy.INFERABLE: 0.82,
}
