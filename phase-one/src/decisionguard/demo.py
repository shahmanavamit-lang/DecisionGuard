"""Explicitly simulated actions: no model calls, real employees or external sends."""
from dataclasses import asdict
from .contracts import ActionRequest, Grant, Permission, TaskScope
from .runtime import Gateway, SyntheticTools

# Public demonstration value, never a real access token.
DEMO_CREDENTIAL = "decisionguard-local-demo"


def build_demo() -> Gateway:
    return Gateway(
        scopes=[TaskScope("procurement-001", 1, "Review the ACME quotation",
                          frozenset({Permission("read", "quotation:acme")}))],
        grants=[Grant("quotation-grant", "procurement-agent", "procurement-001", 1)],
        credentials={DEMO_CREDENTIAL: "procurement-agent"}, tools=SyntheticTools(),
    )


def demo_report() -> dict:
    gateway = build_demo()
    results = [gateway.execute(ActionRequest(request_id, "procurement-001", "quotation-grant",
                                             "read", resource), credential=DEMO_CREDENTIAL)
               for request_id, resource in [("demo-quotation", "quotation:acme"),
                                            ("demo-hr", "hr:salary")]]
    return {"mode": "deterministic_simulation", "phase": 1,
            "results": [asdict(result) for result in results],
            "backend_receipt_count": len(gateway.receipts),
            "hr_read_count": sum(r.resource_id == "hr:salary" for r in gateway.receipts)}
