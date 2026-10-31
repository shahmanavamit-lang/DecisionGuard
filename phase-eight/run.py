"""Run directly from a checkout without third-party packages."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from decisionguard.cli import main
if __name__ == '__main__':
    if len(sys.argv) == 1:
        from decisionguard.launcher import main as start
        raise SystemExit(start())
    raise SystemExit(main())
