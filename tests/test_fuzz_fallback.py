"""Verify saidso works with no rapidfuzz installed (stdlib difflib fallback)."""

import importlib
import sys


def test_difflib_fallback_when_rapidfuzz_absent(monkeypatch):
    # Make `import rapidfuzz` fail, then reload the fuzz module.
    monkeypatch.setitem(sys.modules, "rapidfuzz", None)
    import saidso._matching.fuzz as f

    try:
        importlib.reload(f)
        assert f._HAVE_RAPIDFUZZ is False
        assert f.ratio("hello", "hello") == 1.0
        assert f.ratio("", "x") == 0.0
        assert f.partial_ratio("world", "hello world there") > 0.9
        assert f.partial_ratio("zzz", "hello world") < 0.6
    finally:
        # Restore the real (rapidfuzz-backed) module for the rest of the suite.
        monkeypatch.undo()
        importlib.reload(f)
