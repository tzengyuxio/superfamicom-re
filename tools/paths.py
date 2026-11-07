"""Where the original ROMs are: ~/game-library/_original/sfc/ (~/.claude/re-common.md §1, §11), the only copy.
GAME_LIBRARY overrides the library root, e.g. on another machine. A missing ROM ends with a hint to copy it back."""
import os
import sys

LIBRARY = os.environ.get("GAME_LIBRARY", os.path.expanduser("~/game-library"))
ORIGINAL = os.path.join(LIBRARY, "_original", "sfc")


def _hint(kind, value, tb):
    sys.__excepthook__(kind, value, tb)
    if isinstance(value, FileNotFoundError) and str(value.filename or "").startswith(ORIGINAL):
        print(f"\n{os.path.basename(value.filename)} is not in {ORIGINAL}: copy it back from the backup "
              "(re-common §11), or set GAME_LIBRARY", file=sys.stderr)


sys.excepthook = _hint
