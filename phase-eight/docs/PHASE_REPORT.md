# Phase eight: UI-first v1.1 release

31 October 2026. The user clarified that the HTML/CSS/JavaScript interface is an integral part of the application, not optional. This release corrects startup, presentation and current documentation. Earlier phase folders are preserved as historical snapshots.

- `python3 start.py` from the repository root or phase-eight initializes an empty private workspace when needed and opens the browser. Existing stores are never overwritten. No-argument `run.py` also opens the UI; advanced CLI commands remain available.
- Guided file selection, explicit permission approval, a separate run action and plain-language results replace JSON editing in the beginner workflow. Advanced controls and technical evidence remain available through disclosures.
- The authenticated presentation adapter calls existing import, label, approval and managed-task operations; execution uses the existing controller/broker. Enforcement, behavior learning, worker processing, receipts, containment, budgets and schema 4 remain unchanged.
- Setup is a sequence of existing transactions. Partial failures grant no worker access; the UI explains reconciliation and never automatically retries a run.
- 145 cumulative tests pass. The full 160-case evaluation passes all declared gates. Results/source hashes were refreshed. JavaScript syntax passes.
- Browser verification covers real file selection, approval, execution, statistics, persisted results, reload, keyboard dismissal, desktop and mobile. See UI_VERIFICATION.md.
- Release packaging remains reproducible and dependency-free. The clean extracted source is checked in an environment without pip packages. The local runtime needs no external API/key/model or Node server.

See RELEASE.md for backup, locked restore, retention and known boundaries. The first guided analysis is deterministic statistics, not semantic AI or an attack benchmark. This remains a bounded prototype, not a production-readiness guarantee.
