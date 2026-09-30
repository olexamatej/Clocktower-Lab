# Reference games

## Sects & Violets: ten Luna players

[luna-fast-sects-and-violets-10-seed-42.json](luna-fast-sects-and-violets-10-seed-42.json) is the completed real Codex game started on September 30, 2026.

- Script: Sects & Violets, using the [supported ten-character roster](../../docs/SECTS_AND_VIOLETS.md); ten distinct personas; setup seed 42.
- Provider/models: Codex CLI, five `gpt-5.6-luna` and five `gpt-6-luna` players, alternating seats. All used low reasoning and fast service, with no total token cap.
- Result: **Evil wins** — a day ended without an execution while the Vortox was alive and healthy.
- Recorded activity: 166 decisions, 458 events, 3,182,332 input tokens and 26,135 output tokens.
- Original run ID: `79a04a65c8d1440f80cb536303241a02`.

```sh
clocktower import-run examples/runs/luna-fast-sects-and-violets-10-seed-42.json
clocktower web
```

The archive preserves all public and private conversations, role assignments, persona snapshots, and usage. Importing it creates a replay without calling models. This is one game using a fixed supported roster, not a comparison benchmark or a demonstration of full Sects & Violets support.

## Bad Moon Rising: ten Astra ultrafast players

[astra-ultrafast-bad-moon-rising-10-seed-42.json](astra-ultrafast-bad-moon-rising-10-seed-42.json) is the completed real Codex game started on September 30, 2026.

- Script: Bad Moon Rising; ten players with ten distinct personas; setup seed 42.
- Provider/model: Codex CLI, `gpt-6-astra`, ultrafast service tier, low reasoning effort for every player.
- Result: **Good wins** — no living Demon remains.
- Recorded activity: 146 decisions, 384 events, 2,992,282 input tokens and 48,187 output tokens.
- Original run ID: `b60a0eafae20459980b0f924987c5ad9`.

The game initially stopped on day 2 after 104 decisions because its next request would exceed the two-million-token budget. It was resumed with the token cap removed, retaining the same run ID, history, private notes, and cumulative usage. Earlier model decisions were restored from the record, not requested again. This archive contains the completed game.

```sh
clocktower import-run examples/runs/astra-ultrafast-bad-moon-rising-10-seed-42.json
clocktower web
```

## Trouble Brewing: seven Codex players

[codex-trouble-brewing-seed-42.json](codex-trouble-brewing-seed-42.json) is the full archive of the real Codex game run on September 30, 2026, using the project's default personas. It contains model-generated decisions and conversations, not mock responses.

- Script: Trouble Brewing; seven players; setup seed 42.
- Provider/model: Codex CLI, `gpt-6.1-sol`, low reasoning effort.
- Result: **Good wins** — no living Demon remains.
- Recorded activity: 64 decisions, 194 events, 1,135,356 input tokens and 16,561 output tokens.
- Original run ID: `8ffcf26cd48e41b782065b1735dd8815`.

Open the app, choose **Run archive → Import run**, and select the JSON file. Alternatively, from the repository root:

```sh
clocktower import-run examples/runs/codex-trouble-brewing-seed-42.json
clocktower web
```

Import creates a separate replay and does not call any models. The archive includes all roles, private conversations, and embedded persona snapshots; the original persona files are not needed to review it. Choose a player perspective to inspect only what that player could see, or Storyteller to inspect the full game.

The Trouble Brewing run predates the Astra ultrafast / Bad Moon Rising preset. These individual games are examples, not a win-rate benchmark. The setup seed does not make live model responses reproducible.
