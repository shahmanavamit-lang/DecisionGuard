"""Start DecisionGuard's browser interface; no installation or API key required."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent/'src'))
from decisionguard.launcher import main
if __name__ == '__main__': raise SystemExit(main())
