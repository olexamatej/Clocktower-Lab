# Clocktower Lab

This is a clean rewrite. Never write to production.

## Architecture
- `clocktower/bmr.py`: Bad Moon Rising rules extending the shared state machine.
- `clocktower/sv.py`: the supported ten-player Sects & Violets roster; other S&V setups are rejected.
- `clocktower/archives.py`: versioned full-run import/export; imports are inert replays.
- `clocktower/engine.py`: authoritative game state, script abilities, legal actions and audience-scoped events. No network, filesystem, or model calls.
- `clocktower/roles.py`: Trouble Brewing script registry and role instructions.
- `clocktower/config.py`: shared strict configuration schema and capability validation.
- `clocktower/providers.py`: backend-only HTTP adapters; no secrets in persisted objects or exceptions.
- `clocktower/runner.py`: bounded autonomous game orchestration, memory, usage and interruption.
- `clocktower/storage.py`, `personas.py`: atomic JSON / Markdown persistence.
- `clocktower/api.py`, `cli.py`: same runner and storage used by both interfaces.
- `clocktower/web/`: local browser application; all game decisions belong on the backend.

## Development
Install with `python3 -m venv .venv` and `.venv/bin/pip install -e '.[dev]'`. Start `.venv/bin/clocktower web`. Run `.venv/bin/pytest`, `.venv/bin/mypy clocktower`, `.venv/bin/ruff check clocktower tests`, and `.venv/bin/python -m build`. Browser smoke uses Playwright Chromium; install it with `.venv/bin/playwright install chromium`.

Keep rules independent of transport. Extend the script registry and rules dispatch, not the UI, for future scripts. Add regression coverage for rules interactions and information boundaries. Keep persisted schemas versioned. Simulation limits interrupt games and never award victory.

## Security and information boundaries
The engine alone owns actual roles, drunkenness, poisoning and storyteller choices. Player prompts are assembled solely from that player's filtered observation and Markdown persona. Never pass the complete config, other memories, or omniscient events to providers. Public night deaths are announced at dawn; hidden night actions must not leak timing/content through projections. View selection is an inspection feature for a trusted local operator, not multi-user authorization. Bind the server to loopback; reject cross-origin mutations. Credentials come from backend environment references; never store credential values in configs, events, prompts or HTTP error bodies.

## Personas and providers
Each persona is Markdown with a `# Name` followed by `## Communication`, `## Decisions`, `## Uncertainty`, `## Trust`, `## Bluffing`, and `## Role adaptation`. Persona instructions describe behaviour only, never authoritative role/alignment or permissions. Template assignment copies into an independent player file. Providers must explicitly validate generation parameters; unknown options are errors, never silently dropped. Network retries and action recovery are bounded and auditable.
