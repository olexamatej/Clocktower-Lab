# Validation record

Validated on 30 September 2026 with Python 3.14.2 and Chromium installed by Playwright. The application targets Python 3.11+. This environment had no live provider credentials.

## Executed checks

| Check | Observed result |
| --- | --- |
| `pytest -q` | **49 passed in 19.53 seconds**, including real Chromium smoke |
| `ruff check clocktower tests` | Passed |
| `mypy clocktower` | Passed |
| `node --check clocktower/web/app.js` | Passed |
| `python -m build` | Wheel and source distribution produced; final packaging includes this record |
| Wheel inspection | Three web assets and ten Markdown persona templates present |
| Source distribution inspection | Documentation, example configurations and AGENTS.md present |

The only test warning is an upstream Starlette/httpx test-client deprecation warning. Browser/server tests require permission to bind a loopback port in restricted sandboxes; they passed with that permission. The embedded preview browser was unavailable, so verification used the real Chromium smoke test and inspection of its screenshots.

## Requirement coverage

| Requirement | Evidence |
| --- | --- |
| Standard 5–15 player setup | `test_setup_counts_and_unique_characters` checks every count over ten seeds, Baron modifiers, uniqueness and bluff exclusions |
| Complete autonomous games | `test_offline_complete_games` reaches legitimate results at 5, 7, 10 and 15 players |
| Character interactions | Engine tests cover Drunk secrecy, poison/protection, succession, delayed Scarlet Woman information, Saint, Virgin, Butler, Slayer, Mayor, Fortune Teller red herring, Ravenkeeper, Undertaker, zero-Outsider Librarian, sole-Townsfolk Washerwoman and registration |
| Legal actions and votes | Invalid targets and non-Boolean votes rejected; once-only dead votes, master restriction, tie high-water mark and nomination effects verified |
| Hidden information | Recipient-filtered engine/API views, private messages, reserved viewer names, Drunk role projection and mixed-provider prompt isolation verified |
| Independent providers | One completed game routes players through offline OpenAI, Anthropic, e-INFRA and custom-compatible HTTP endpoints; header and request contracts checked |
| Limits and recovery | Turn interruption, cancellation during a provider call, bounded malformed-action fallback, rate-limit retry and safe malformed-response errors verified |
| Shared defaults and overrides | Per-player generation can override or explicitly remove inherited settings without affecting others |
| Personas | Ten substantial templates, independent player Markdown files, immutable built-in templates and persisted custom edits verified |
| Browser workflow | Chromium configures a game, creates/edits/previews a persona, saves and starts the game, changes view, rewinds/steps/replays, opens archive, and checks 15-player layout |
| CLI/web interoperability | A web-saved configuration is run by the ordinary CLI subprocess; its completed record reopens through the same public/player API used by the visualizer |
| Durable runs | Atomic JSON snapshots include configuration, persona text, seed, model assignments, actions, messages, results and usage; interrupted records remain inspectable |
| Local execution and packaging | One `clocktower web` command serves backend and frontend; CLI uses the same engine/provider/schema/persistence modules; wheel contains runtime resources |
| Reference/attribution | Upstream source and linked visualizer inspected, MIT notice preserved; official rules and provider references documented in REFERENCES.md |

## Browser evidence

- [Configuration screen](screenshots/setup.png)
- [Completed game and replay](screenshots/frontend.png)
- [15-player seating and interrupted result](screenshots/fifteen-players.png)

The laptop checks use 1440×1000 and 1280×800 viewports. Larger games use a numbered seating grid to keep names, provider/model labels and state readable without overlap. The screenshots show actual locally executed games, not mockups.

## Live-provider status and limits

No `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `E_INFRA_API_TOKEN`, or `COMPATIBLE_API_KEY` was present. **Live generation and account-specific model availability remain unverified.** Endpoint/authentication formats were checked against official documentation, and request/response contracts were exercised with mock HTTP transports. No live paid API calls were made.

Supported scope is Trouble Brewing with 5–15 players. Travellers, Fabled, additional scripts and human seats are outside this release. Conversations use explicit turns and configured rounds; storyteller choices use documented deterministic policies rather than human judgment. Interruptions are inspectable but not resumable. Public/player views are visibility projections for a trusted local operator, not authorization for a multi-user service. Actual model-specific capability rejection can occur after local validation; costs depend on optional configured prices, and unknown tokenizers use conservative byte-based limits. Transport failures can leave provider-side usage unobservable.
