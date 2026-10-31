# Browser interface: normal application startup

Run `python3 start.py` from the repository root or phase-eight. The launcher initializes an empty store if needed, opens the browser, and prints a one-use access code. The UI is an integral part of the project; advanced CLI workflows remain available for administration and testing.

Start here guides the owner through selecting a UTF-8 file (1–200,000 bytes), reviewing two exact permissions and a byte budget, explicitly approving, and explicitly running. The adapter calls existing import/label/approve/manage operations. Execution uses the existing fresh-context controller and broker. No policy engine, behavior model, containment rule, receipt logic, worker implementation or schema is replaced. Setup is not one transaction: partial failures may leave an imported resource or approval. No worker grant exists until an explicit start. Reused setup/run IDs are rejected; lost responses must be reconciled, never automatically retried.

Results uses ordinary status words and shows text-statistics previews from completed saved notes. Technical records are available in disclosures. Advanced controls retain permission JSON, custom worker plans, comparisons, owner review and containment. Importing is a snapshot; original files are untouched. The guided path is intentionally narrow. Larger imports (up to the existing 1 MiB engine limit), resource labeling and behavior training remain advanced CLI operations.

## Interface architecture and boundary

The Python backend remains authoritative. The browser interface is the normal application entry point. Advanced CLI workflows remain available for administration and testing.

## Design and entry points

`control.py` owns consistent bounded read models and shared administration operations. `console.py` serves three allowlisted assets and a narrow HTTP adapter. `web/` contains HTML, CSS and plain JavaScript; no package manager, CDN, analytics, or build step is used at runtime. `start-fresh-worker`, `overview`, and version-checked CLI approvals reuse the backend without opening a listener.

Read endpoints: `/api/session`, `/api/snapshot`, `/api/events?before=SEQUENCE`, `/api/graph?task=ID`, `/api/action?id=ID`. Only static assets and the login route are accessible before authentication. Action details may contain input or note content and are owner-only forensic access, never worker endpoints.

Owner POST operations under `/api/admin/`: `prepare`, `approve`, `start`, `review`, `dispatch`, `continuation`, `contain`, `stop`. Exact payload fields are validated by `control.py` and the narrow `onboarding.py` adapter. POST responses can represent a denied/held/blocked outcome even when HTTP itself succeeded; inspect the returned state. There is no arbitrary command, file path, SQL, plugin or external tool endpoint.

## Local owner boundary

- Fixed `127.0.0.1` binding; no LAN/public bind option. Exact Host and Origin checks reject foreign origins, DNS-rebinding hostnames and ambiguous headers. Fetch metadata rejects cross-site/same-site browser requests.
- Owner UID and database mode 0600 are checked before serving and on each transaction. Existing phase-five schema 4 is supported; earlier schemas are rejected.
- Random one-use terminal login code: ten-minute validity, maximum ten failed attempts. One in-memory browser session per server startup, up to eight hours, with HttpOnly/SameSite=Strict cookie and independent CSRF token. Logout removes the server session; restart creates a new code and invalidates old sessions. Cookies are local HTTP, not TLS cookies; never expose this server through a proxy or tunnel.
- JSON-only writes, 2 MiB maximum body, duplicate-field/nonfinite-number rejection, 15-second socket timeout. No directory serving, CORS enablement, or request-body logging.
- Content Security Policy excludes remote assets, inline script, framing and arbitrary connections. Runtime text is inserted with text nodes. No `innerHTML` or script evaluation of document content.

This is a single-owner development console, not a production multi-user security boundary. Local owner processes, the browser profile, and browser extensions remain trusted. The standard-library threaded server has no production availability guarantee or aggregate request/concurrency quota. Do not expose it to untrusted local users or hostile clients. No promise is made against same-UID processes reading memory/files or bypassing the gateway.

## State, bounds and recovery

Overview counts cover the entire store, but each entity list is bounded to 200 records. Actions/runs use recent records; tasks sort by ID. Partial views are labeled. Timeline pages traverse older events without re-executing work. Graph responses cap at 200 nodes/800 edges; drawings cap at 60 nodes, with a text alternative for the returned graph. Missing nodes or a partial graph never establish safe independence. CLI inspection remains available for complete records.

A refresh shows recorded state at a point in time, not a live process heartbeat. A `running` record may survive a broker crash. The UI distinguishes attempts from receipts, risk priority from probability, and cold-start/stale-profile evidence from trained confidence. Run comparisons do not automatically label runs benign or malicious.

The browser never automatically retries a mutation. On lost response it displays an unknown-outcome warning; inspect the unique run/request ID, events and receipts before any deliberate retry. A store failure is an error, not an empty healthy dashboard. Timeline or graph failures are separate from other loaded panels.

Fresh starts are explicitly owner-authorized: current scope version, new run ID, supplied plan, reason, new grant/context/memory. They preserve budgets and prior receipts. Context preparation and worker launch are separate transactions; interruption can leave unused authority, recorded by `console_fresh_context`. Reconcile and revoke that grant through the CLI when needed. Restarting is not automatic contaminated-context repair. Stop revokes authority; it does not promise an instantaneous OS kill or undo committed effects.

Approving scope vN+1 checks the expected current version in the same transaction. It invalidates old scope-bound grants. Behavior review cannot override hard policy and remains separate from dispatch. The corrected continuation preview honors a still-valid review; dispatch always rechecks current state.

## References informing this adapter

Python documents the standard-library server's limited security scope: [http.server](https://docs.python.org/3/library/http.server.html). Origin checking, session-bound CSRF protection and SameSite defense in depth follow the principles in the [OWASP CSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). These references are design inputs, not external audits or certification.
