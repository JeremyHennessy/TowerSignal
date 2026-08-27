# Diagnostic 016F — current WebKit session persistence

This branch tests one hypothesis only: the production authentication code may be valid while the repository's pinned Playwright 1.49.1 / WebKit 18.2 hosted verifier is too old to reproduce the current cross-origin Neon Auth cookie behavior.

The diagnostic does not change production application code, authentication code, data, UI, scoring, history, or deployment behavior. It overlays `@playwright/test@1.62.1` inside a PR-only workflow and runs the existing iPhone authenticated E2E suite against the already-deployed `main` application.

Interpretation:

- If the existing iPhone suite passes under current WebKit, update the permanent verification harness only and prove the normal Pages chain.
- If it fails with the same session-loss behavior, reject this hypothesis and inspect the actual Neon Auth cookie/session boundary before changing production.

Do not merge this diagnostic branch.