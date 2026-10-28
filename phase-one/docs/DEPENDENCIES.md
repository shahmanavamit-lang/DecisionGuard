# Dependencies and licensing

Runtime and tests use only the Python 3.11+ standard library. `requirements.txt` is intentionally comment-only. No model service or API key is required.

Optional editable package installation uses setuptools (declared in `pyproject.toml`), which may be downloaded by pip. The direct checkout commands do not require a build backend. Python and setuptools retain their own licenses and are not redistributed here.

Repository CI uses GitHub's `actions/checkout` and `actions/setup-python`; those actions retain their upstream licenses. They are development infrastructure, not application runtime libraries. CI runs Python 3.11–3.14; local validation uses the installed interpreter recorded in the phase report.

Original code in this phase is MIT-licensed, with the license included both at repository root and within this standalone phase folder. No third-party research implementation, private document, vendor dataset or presentation export is included.
