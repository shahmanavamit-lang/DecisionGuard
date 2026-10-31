> Historical phase-six decision. Its optional-UI rollout is superseded by the required UI startup and guided experience described in CONSOLE.md.

# ADR 006: backend-first owner controls with an optional custom console

Status: accepted for phase six, 29 October 2026.

The roadmap called for an operator console. The user clarified that backend completion remains primary and that a custom UI is a later preference over Streamlit. Retain the completed interface as optional, do not make subsequent work depend on it, and expose new owner operations through the CLI.

Use a shared Python control/read-model layer over existing SQLite transactions and enforcement. The browser is a thin local adapter, not a parallel policy implementation. Vanilla HTML/CSS/JavaScript replaces the roadmap's proposed React/TypeScript stack here to preserve a zero-install runtime; this is an implementation choice, not a claim that frameworks are impossible. No Node process, npm installation, CDN or hosted service is required to run the project.

Keep schema 4: the new projection and approval guard require no database migration. Historical snapshots stay intact. Old continuation-preview behavior is corrected in the current cumulative snapshot only.

Local owner authentication is a randomly generated one-use code and in-memory session, not a cloud/API credential. The console is loopback-only and opts in explicitly. Production multi-user access, deployments, evaluations and arbitrary-agent sandboxing remain separate work.
