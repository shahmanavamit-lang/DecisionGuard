"""Start the current cumulative DecisionGuard application."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent/'phase-eight/start.py'), run_name='__main__')
