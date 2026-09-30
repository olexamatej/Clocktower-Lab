# Reference game

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

This is one recorded run, not a win-rate benchmark. The setup seed does not make live model responses reproducible. It predates the Astra ultrafast / Bad Moon Rising preset.
