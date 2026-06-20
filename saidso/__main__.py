"""Enable ``python -m saidso`` as an alias for the ``saidso`` CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
