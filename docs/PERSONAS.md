# Markdown persona format

The persona's first heading is its name. Six level-two headings give the guided editor a stable structure:

```markdown
# Patient investigator

Optional introduction describing the player's style, not game facts.

## Communication
Ask one precise question at a time and summarize the answer fairly.

## Decisions
Compare at least two explanations before choosing a nomination or vote.

## Uncertainty
Say what would change your mind; separate a guess from received information.

## Trust
Track promises and corroboration without treating friendship as proof.

## Bluffing
Keep claims consistent and remember which details you have disclosed.

## Role adaptation
As good, seek the Demon. As evil, protect your team with plausible alternative explanations.
```

Each section must contain text. Files must contain 100–20,000 characters. The current format uses ordinary Markdown, not YAML frontmatter. Extra prose may be included; the guided editor updates the six sections in the same underlying document. Preview safely renders headings and paragraphs as text and never executes HTML.

Write new files under the active `personas/` storage directory, for example `data/personas/my-investigator.md`. Select them in the web app after refreshing the Persona library, or use `"persona": "my-investigator.md"` in a player's JSON configuration. `builtin:analyst` refers to the shipped read-only template.

Saving a game replaces template references and duplicate assignments with independent copies. Duplicating a configuration copies all its player personas. Editing one player's template selection in the web interface creates a private copy immediately. A run snapshots every assigned document. Persona paths are contained within the persona root, including symlink resolution; arbitrary filesystem paths are rejected.

Personas are behavioural guidance below the rules instruction. They cannot choose an actual role or team, receive the Grimoire, expand the observation, call tools, or perform an illegal action. A Spy sees the Grimoire because of the engine's ability resolution, not because its Markdown requests it. A poisoned or Drunk player gets only the information supplied by the storyteller policy.
