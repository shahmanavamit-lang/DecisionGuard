"""Local CLI. Demo credentials are never accepted from proposed action JSON."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .contracts import ActionRequest, ValidationError
from .demo import DEMO_CREDENTIAL, build_demo, demo_report

MAX_REQUEST_BYTES = 16_384


def unique_keys(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON keys are not accepted")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DecisionGuard phase-one local security demo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Run the allowed quotation and denied HR scenario")
    action = sub.add_parser("check", help="Execute one request against synthetic tools")
    action.add_argument("request", type=Path, help="Action JSON file")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            report = demo_report()
            code = 0
        else:
            with args.request.open("rb") as stream:
                raw = stream.read(MAX_REQUEST_BYTES + 1)
            if len(raw) > MAX_REQUEST_BYTES:
                raise ValidationError("request file exceeds 16 KiB")
            request = ActionRequest.from_dict(json.loads(raw, object_pairs_hook=unique_keys))
            result = build_demo().execute(request, credential=DEMO_CREDENTIAL)
            report = asdict(result)
            code = 0 if result.decision.outcome == "allow" else 3
    except (OSError, ValueError) as error:
        print(json.dumps({"error": "invalid_request", "message": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return code
