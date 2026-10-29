# Offline dependencies and license

Runtime and tests use Python 3.11+ and its standard library, including SQLite via `sqlite3`. No external APIs, network clients, hosted models, API keys or pip packages are used by checkout execution. `requirements.txt` is intentionally comment-only. Python and SQLite retain their upstream licenses; neither is vendored here.

`pyproject.toml` provides optional packaging metadata. Its build backend is setuptools; package building may require that tool to already be installed in an offline environment. The documented `python run.py` workflow avoids packaging and does not download anything.

GitHub Actions downloads development infrastructure to check the public repository. This is separate from the application: running DecisionGuard itself does not require GitHub or network access. Project source is MIT-licensed; the full license is included in this standalone phase folder and at repository root.

All business input is supplied by files. Tests create temporary synthetic data and delete it after each run. Templates contain editable policy examples and identifiers, not bundled business datasets. No prior research code or private presentation material is included.

Phase-four addendum: these inherited notes describe the foundation. See CONTAINMENT.md for schema 3, managed contexts, output delivery, containment and continuation; phase four requires a fresh database.

Phase-five addendum: fixed worker process integration, broker authority and run recovery are described in WORKERS.md. Schema 4 requires a fresh store. Inherited notes describe earlier foundations; no arbitrary hostile-code sandbox is claimed.
