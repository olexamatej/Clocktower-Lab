# Clocktower Lab

Clocktower Lab is a local Blood on the Clocktower simulator where AI agents argue, bluff, and try to outsmart each other. Give each player their own model and Markdown persona, configure games through the web interface or CLI, and inspect what happened through public, individual-player, or omniscient replays. The goal is to study how different language models build trust, persuade others, and deceive, including whether Chinese-developed models lie more often than other models under comparable roles, personas, and game conditions, and whether Mistral starts citing compliance rules when asked to bluff.

## Install and start

Requires Python 3.11 or later. From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
clocktower web
```

Open **http://127.0.0.1:8000**. The single `clocktower web` command starts the backend and serves the bundled browser application. Node and a frontend build are not required. Use `clocktower web --port 8080` to choose another port. The application binds to loopback and is intended for one trusted local operator; it is not a multi-user server.

The default configuration uses the offline mock provider. Click **Start game** without any API keys. A completed game has a rules-based good/evil result. A stopped or resource-limited game is **interrupted**, with no winner.

## Web workflow

1. Choose 5–15 players, names and clockwise seating. Leave random character selection enabled, or choose a legal Trouble Brewing composition under **Character setup**.
2. Select each player's provider and model. Expand **Endpoint, generation & memory** for endpoint URL, credential environment-variable name, output/context limits, timeouts, retries, prices, memory and generation parameters. Per-player settings inherit shared defaults. Clearing an inherited generation field explicitly removes it for that player (`null` in JSON overrides).
3. Select a persona and click **Edit**. The guided editor and Markdown editor modify the same document. Preview it or import an existing `.md`. Editing a template creates a copy. Saving a configuration ensures every player has a different file.
4. Adjust storyteller policy, seed, conversation rounds, private conversations and resource limits. **Validate** gives actionable errors. Save, duplicate, import or export configurations.
5. Start the game and inspect the seating view and timeline. Select a perspective, filter events, stop a live game, or use rewind, step, playback speed and the position slider. Previous runs appear in **Run archive**.

Run data uses one format whether it comes from the browser or CLI. A CLI run saved to the same data directory appears in the archive on refresh. **Export visible events** exports only the selected perspective, while complete authoritative records remain in `data/runs/`.

## Headless CLI

```sh
# Complete offline game:
clocktower demo --players 7

# Create an example config:
clocktower demo --write my-game.json

# Run the same JSON exported by the web interface:
clocktower validate my-game.json
clocktower run my-game.json

# Exercise a live-provider config offline:
clocktower run examples/mixed-providers.json --mock

# Use the same nondefault storage location for both interfaces:
clocktower --data /path/to/lab-data web
clocktower --data /path/to/lab-data run my-game.json
```

`CLOCKTOWER_DATA` supplies the default data directory; otherwise it is `data/` relative to the working directory. Keep the same directory between sessions. It contains JSON configurations, independent `.md` personas and run records. Exported configurations reference persona paths relative to `data/personas/`; copy the associated files when moving a configuration to another machine. Built-in references are portable without copying.

## Play with Codex

Install the Codex CLI and run `codex login` once. Select **Codex CLI / ChatGPT login** in the browser, or run:

```bash
clocktower run examples/codex.json
```

The example uses `gpt-6-astra`, the `ultrafast` service tier, seven players, and low reasoning effort. Set the model to one available to your Codex account. Requests use your existing Codex login and its usage limits; no OpenAI API key is needed for a ChatGPT login.

Each decision runs a fresh `codex exec` session in a temporary directory with user config, project instructions, shell, web search, plugins, and other integrations disabled. Only that player's filtered observation and persona are supplied. Structured output selects one legal option; the engine still validates the resulting action. Stopping a game cancels the active CLI process. Requires a recent CLI supporting `--ignore-user-config`, `--ephemeral`, and `--output-schema`.

Codex supports `reasoning_effort` and explicit provider-default/Fast/Ultrafast service tiers here; HTTP endpoint and credential settings do not apply. CLI failures interrupt the game rather than silently replacing players with mocks. `timeout_seconds` bounds each call; CLI transport retries are managed by Codex itself, not the HTTP retry field. Codex reports input/output usage, but this integration cannot enforce the HTTP `max_output_tokens` generation cap: that field is used for context/budget reservation only. The total token limit is checked between decisions and can be exceeded by the last call. Pricing is unavailable unless supplied explicitly.

See the official [non-interactive Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode).

## Credentials and providers

Set credentials in the **backend process environment**, then start the web app or CLI:

```sh
export OPENAI_API_KEY='your-key'
export ANTHROPIC_API_KEY='your-key'
export E_INFRA_API_TOKEN='your-key'
clocktower web
```

Never enter a key into a model name, persona, URL or configuration. Configurations accept environment-variable **names**, never API key fields. Provider errors omit response bodies and request headers. No credentials are sent to the browser, included in prompts, or stored in run records. There is no dotenv auto-loader; your shell or process manager controls the environment.

| Provider | API | Default base URL | Default credential variable |
| --- | --- | --- | --- |
| OpenAI | Chat Completions | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| Anthropic | Messages | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` |
| e-INFRA | OpenAI-compatible Chat Completions | `https://llm.ai.e-infra.cz/v1` | `E_INFRA_API_TOKEN` |
| compatible | Chat Completions | Required | `COMPATIBLE_API_KEY` (optional for local unauthenticated servers) |
| mock | Local observation-only policy | None | None |

Override the endpoint and credential variable per player. URLs must use HTTPS, except loopback HTTP for local inference servers; userinfo, query strings and fragments are rejected. Redirects are not followed with credentials. The configured server is trusted to receive that player's private game view.

For e-INFRA, create an **API key**, not a JWT, in the Open WebUI account settings. CERIT documents Bearer authentication, `/v1/models`, and `/v1/chat/completions`; not every OpenAI endpoint is supported. Use `clocktower models einfra` or **List endpoint models** to retrieve available model IDs. Model aliases can change their underlying model. See [provider reference](docs/REFERENCES.md).

Generation options are capability-checked. Common chat models accept temperature, top-p and stop sequences. The compatible/OpenAI/e-INFRA adapters also support seed and frequency/presence penalties; Anthropic supports top-k. Reasoning OpenAI families use reasoning effort rather than those sampling parameters. Unknown or incompatible settings fail validation rather than being silently ignored. Actual model-specific restrictions can also produce a safe provider error; the platform cannot infer every custom endpoint's capabilities. Use a workspace-scoped Anthropic API key. Advanced Anthropic thinking/workspace-routing and non-chat modalities are not exposed.

Retries for network failures, HTTP 429 and server errors are bounded. Invalid JSON/actions receive bounded correction attempts, then a recorded legal fallback. A connection failure or exhausted resource limit interrupts the run. User-provided per-million-token prices enable cost estimates; unknown pricing is shown as unavailable. Missing provider usage is conservatively estimated from bytes. Provider-reported usage after transport failures may be unknowable.

## Persona format

See [persona format and manual authoring](docs/PERSONAS.md). Ten complete personas are bundled: Analyst, Skeptic, Diplomat, Interrogator, Observer, Gambler, Contrarian, Performer, Strategist and Improviser.

```sh
clocktower persona list
clocktower persona create 'Patient investigator' --from builtin:observer
clocktower persona validate data/personas/custom/FILE.md
```

Custom files persist across restarts. To add one manually, write it under `data/personas/` and refer to its relative `.md` path. Persona text affects style and strategy, never actual role, alignment or legal permissions. Each run snapshots the text it used, so later editing does not change replay history.

## Portable games

Choose **Export full game** in a replay to download a versioned JSON archive containing the configuration, all role assignments, private/public events, persona snapshots, and usage. **Export visible events** remains a view-only export and is not an importable full archive. Full archives include spoilers and private conversations.

Use **Import run** in Run archive to add an archive as a new replay. Imports never overwrite another run, restore arbitrary files, or start model calls. In-progress snapshots are imported as interrupted replays, not resumable live processes. The maximum archive size is 50 MiB.

Three [completed reference games](examples/runs/README.md) are included: seven-player Trouble Brewing with `gpt-6.1-sol`, ten-player Bad Moon Rising with `gpt-6-astra` ultrafast, and the supported ten-player Sects & Violets roster with GPT-5.6 Luna and GPT-6 Luna on fast mode. Good won the first two; evil won Sects & Violets when a day ended without an execution under Vortox. Import their full archives to review the actual conversations and decisions.

Local interrupted games can be continued with `clocktower resume RUN_ID`. The runner reconstructs the state from recorded decisions, verifies the complete event history against the current rules, and restores private notes and cumulative usage before making new model calls. It retains the run ID and saves the interrupted record under `data/resume-backups/`. Imported archives remain replay-only. A rules/history mismatch prevents resuming.

Use `clocktower resume RUN_ID --max-tokens 0` to remove the token cap, or supply a larger total budget including tokens already consumed. A token budget of `0` also means unlimited in game setup. Other game limits still apply; the runtime allowance starts again for the resumed process.

```sh
clocktower export-run RUN_ID game.json
clocktower import-run game.json
```

## Bad Moon Rising

Choose **Bad Moon Rising** in the Scenario selector, or use `examples/bad-moon-rising.json` for seven Codex/Astra ultrafast players. The role guide, player prompts, setup counts, and night order follow the selected script. All 25 BMR characters have engine rules, including the four Demons, resurrection, drunkenness, protection, and the Mastermind's extra day. See [BMR simulation policy](docs/BAD_MOON_RISING.md).

The local `configs/next-game.json` saved configuration, when present, is loaded on the setup screen at startup. It prepares a game; it does not start one automatically.

## Sects & Violets example

`examples/sects-and-violets.json` configures ten players alternating GPT-5.6 Luna and GPT-6 Luna, with low reasoning and fast service via Codex. It uses the supported ten-character roster and no total token cap. See [Sects & Violets support](docs/SECTS_AND_VIOLETS.md) for the exact roster, rules, and limitations. The full script is available for reference and bluffs, but other Sects & Violets setups are not yet implemented.

```sh
clocktower run examples/sects-and-violets.json
```

## Watching a game

Each player has a separate information context. For every decision, the Codex provider starts a fresh request containing that player's persona, the script rules, their role and private information, public history, whispers they participated in, their own saved notes, and the available legal actions. Other players' private information and notes are excluded. Players act sequentially when the rules engine requests a decision; they are not continuously running Codex chats.

The Python rules engine acts as Game Master: it owns the full state, resolves abilities, and determines what each player learns. A player's response chooses an action and may replace their saved notes for the next request. With recent-history memory, older events are trimmed when the configured context budget is exceeded, while identity and initial role/team information are retained. The ten-player Astra example uses a 128,000-token context budget per request. This is separate from the total game token budget; removing the latter does not remove the context limit.

The viewer shows the selected scenario, both teams' victory conditions, and a Game Master / Storyteller panel. The Game Master is the automated rules engine: it handles night abilities, private information, voting, and victory announcements.

Conversation cards show a numbered speaker, a named recipient (or **Everyone**), and a public-speech or private-whisper label. Gold cards are Game Master announcements. Use **Detailed log** to inspect technical records. The role roster follows the replay position and selected perspective; **Reveal all roles · Storyteller view** exposes the actual assignments. Public and player views keep other roles hidden. The expandable character guide lists every possible role in the selected script, not the current game's assignments.

## Rules and simulation policy

[Rules and storyteller policy](docs/RULES.md) describes supported Trouble Brewing mechanics and the distinction between official rules and simulation pacing. Trouble Brewing and Bad Moon Rising support 5–15 players. Sects & Violets currently supports only its documented ten-player roster. Travellers, Fabled, other scripts, and human-controlled seats are not currently implemented.

The seed reproduces setup, mock decisions and storyteller choices **given the same action sequence**. Real model generation is nondeterministic, even where a generation seed is accepted. Replays render recorded events; they never call the model again.

Day, turn, runtime, and context limits always apply; the total token cap can be disabled with `0`. `recent` memory pins identity and initial evil-team information and trims the oldest remaining observations to fit. `notes` additionally keeps only the most recent 30 non-pinned events plus the player's own notes. `full` preserves history and interrupts rather than silently truncating. The byte-based context bound is deliberately conservative for unknown provider tokenizers. Persona/rules/legal-actions must fit even after history is removed.

## Development and verification

```sh
pip install -e '.[dev]'
playwright install chromium
pytest -q                         # includes real browser smoke
pytest -q -m 'not browser'        # offline engine/provider/API coverage
mypy clocktower
ruff check clocktower tests
node --check clocktower/web/app.js  # optional JS syntax check, Node 18+
python -m build
```

See [AGENTS.md](AGENTS.md) for architecture and hidden-information conventions, and [validation record](docs/VALIDATION.md) for observed results and remaining limitations. Browser tests launch an isolated loopback server and use temporary storage. Provider protocol tests use mock HTTP transports, not live paid services.

## Troubleshooting

- **Missing credential:** export the reported variable in the shell that launches the backend, then restart it.
- **HTTP 400/404:** verify the model ID, endpoint base URL (including `/v1`) and generation support. Use model discovery; a listed model may still be unsuitable for chat.
- **Interrupted/context limit:** raise context limits within the model's real capacity, shorten the persona, reduce conversations, or select recent/notes memory.
- **Interrupted/runtime or tokens:** raise the specific configured limit if desired. The platform never labels this a draw or victory.
- **Invalid setup:** check the required category counts in the validation message. Baron adds two Outsiders and removes two Townsfolk.
- **Missing custom persona after import:** copy its relative file into the active data directory, or select a built-in template.
- **Old run says interrupted after restart:** its process did not finish. It remains inspectable; in-progress games are not resumable.
- **Port in use:** select a different `--port`. Do not run two backend processes against the same data directory.
