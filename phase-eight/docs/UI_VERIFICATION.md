# UI-first release verification

31 October 2026. The UI is the normal application startup experience. This supersedes earlier optional-interface wording.

Verified in a real browser against a private temporary local store:

- Empty workspace explains purpose, file requirements, permissions and three steps; no records are preloaded.
- Selected the public project README through the actual file picker. Review displayed the selected filename, byte count, allowed actions and budget.
- Approval created an unused task; execution required a separate Run approved analysis click.
- Actual worker execution completed both steps. Word/line/character counts appeared from the saved result; both execution receipts were visible.
- Reopened saved results after server restart and after page reload without replaying work. The result dialog showed plain-language outcomes and statistics, with raw evidence behind a disclosure.
- Keyboard Escape dismissed the result dialog. Existing authenticated HTTP regressions cover Host/Origin/CSRF, unknown outcomes, missing storage and stale scope protection.
- Desktop layout checked at 1366×1000. Mobile checked at 390×844; narrow run tables now become labeled cards so names do not break into unreadable fragments. Technical investigation and advanced controls start collapsed.
- Temporary test server/tab stopped after verification. Preview screenshots are local artifacts, not private data published to the repository.

New automated coverage verifies empty-store startup without overwriting existing data, authentication/CSRF/explicit confirmation for guided setup, upload bounds, duplicate setup/run rejection, out-of-scope denial, and partial setup without worker authority. Full cumulative suite: 145 passing tests. Full 160-case evaluation passes its declared gates. Browser checks are manual checks through browser automation, separate from CI; not a cross-browser accessibility certification.

## Historical phase-six checks

# Browser verification protocol

The console is optional. This protocol is for maintainers, not a prerequisite for using the backend. Its fixture is explicitly synthetic and lives under `tests/`; the application never seeds it automatically.

## Reproduce

From phase-six, choose a new temporary directory and database path:

```sh
python3 tests/browser_seed.py /tmp/decisionguard-browser-check/state.sqlite3
python3 run.py --db /tmp/decisionguard-browser-check/state.sqlite3 console --port 0
```

Open the printed loopback URL in a modern browser. Enter its one-use terminal code. Do not reuse a private/production database for this protocol. Initial expected evidence: 9 tool receipts, 1 held action, 2 quarantined contexts; no worker-run record yet. Trace training is synthetic setup and does not establish detector accuracy.

1. Inspect `supplier-denied`: `denied / outside_scope`, no committed receipt, scope/profile 1, triage factors shown.
2. Inspect `dependent-queued`: `cancelled / contained`, no receipt. The supplier output was consumed by this context; the graph and containment event show the dependency.
3. Inspect `review-held`. Expand its exact proposal. Embedded script-like text is visible as text. Review it with an owner reason. Check continuation: `eligible: true`, `review_valid: true`. Dispatch separately: exactly one note receipt.
4. Dispatch `inventory-queued` with a reason. Current checks allow it; one read receipt commits. The dependent action remains cancelled.
5. Workers: select managed task `review`, supply a new run ID and an explicit read plan over `input` v1, reason and confirmation. It completes a real worker process and shows its receipt. Reusing the ID must not create another effect.
6. Inspect scope and grant details. Scope versions are shown; issued grants are not presented as reusable execution permits.
7. Check keyboard Tab focus, Enter/Space activation, dialog close/Escape, labeled controls, and graph text alternative. At 390px width the document should not overflow horizontally; tables and graph scroll within their own regions. Lock remains available on narrow screens.
8. Stop the server and press Refresh: show stale/disconnected state rather than zeros or success. Restart the server, refresh the page and unlock with the new code. It must not replay prior operations.

## Observed in this delivery

The main incident flow through step 5 passed in the in-app browser against a temporary fixture. Desktop and 390px layouts were inspected, including form labels and bounded horizontal table scrolling. Untrusted markup remained visible as text. Keyboard Tab moved focus into the decision disclosure controls; Escape closed the modal. At 390px the document width stayed at 390px, and Lock remained visible. After stopping the temporary server, Refresh showed “Disconnected · snapshot stale”, retained prior counts, and disabled all owner-action buttons. The preview server and browser tab were then closed.

Python HTTP tests independently cover authentication, expiry, logout, Host/Origin/CSRF checks, malformed input, storage failure, pagination, partial graphs, stale approvals, shared-output propagation, controlled restart, review/dispatch and request replay. They do not replace browser accessibility testing. No screen-reader certification, all-browser compatibility claim, or automated browser fault-injection coverage is claimed. Browser UI checks are not part of CI in this phase.
