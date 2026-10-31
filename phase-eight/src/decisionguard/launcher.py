"""Normal application startup, with advanced CLI retained separately."""
import argparse
from pathlib import Path
import sys
from .contracts import GuardError
from .storage import Store
from .console import serve


def main(argv=None):
    parser=argparse.ArgumentParser(description='Start DecisionGuard in your browser.')
    parser.add_argument('--db', type=Path, default=Path(__file__).resolve().parents[2]/'local/state.sqlite3')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true', help='Print the address without opening a browser')
    args=parser.parse_args(argv)
    try:
        if not args.db.exists() and not args.db.is_symlink():
            Store.initialize(args.db)
        serve(args.db, args.port, open_browser=not args.no_browser)
        return 0
    except (GuardError, OSError, ValueError) as error:
        print(f'Could not start DecisionGuard: {error}', file=sys.stderr)
        print('If the port is in use, try --port 0. Existing workspaces are never overwritten.', file=sys.stderr)
        return 2
