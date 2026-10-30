"""Owner operations: structured JSON output, no external services."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from decisionguard.operations import health, snapshot
from decisionguard.contracts import GuardError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('health'); p.add_argument('database', type=Path)
    for command in ('backup', 'restore'):
        p = sub.add_parser(command); p.add_argument('source', type=Path); p.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        result = health(args.database) if args.command=='health' else snapshot(args.source, args.destination, restore=args.command=='restore')
        print(json.dumps(result)); return 0
    except (GuardError, OSError, sqlite3.Error, TimeoutError) as error:
        print(json.dumps({'operation': args.command, 'error': str(error)}), file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
