# Rules and storyteller policy

The engine supports the complete Trouble Brewing character set with the standard 5–15 player category counts. No Travellers or Fabled are added. At 5–6 players the Demon receives neither bluffs nor Minion identities, and Minions do not learn the Demon. At 7+ the Demon learns Minions and three unused good characters, and Minions learn the Demon and fellow Minions. The Drunk's displayed Townsfolk is reserved from the bluff list. Baron changes the setup only.

## Timing

First night: Poisoner, Spy, Washerwoman, Librarian, Investigator, Chef, Empath, Fortune Teller, Butler. Later nights: Poisoner, Monk, Imp, any Ravenkeeper killed that night, Undertaker, Empath, Fortune Teller, Butler, Spy. Daytime Scarlet Woman transformations take effect when the Demon dies; a new Imp can act the next night. A Scarlet Woman transformed during the day learns its new character at night, while its actual role changes immediately. A night-time successor does not receive an extra attack that night.

Poison clears at the next dusk. Protection applies to the current night. A dead or transformed Poisoner no longer supplies poisoning. Dead characters lose abilities except explicit abilities that function while dead, such as Spy/Recluse registration and the Ravenkeeper's death trigger. Night deaths are hidden until dawn. An ending at night announces the deaths before the result. Executions are distinct from deaths, so an execution of an already dead player does not trigger Saint or give Undertaker a new character.

## Abilities

| Character | Resolution |
| --- | --- |
| Washerwoman / Librarian / Investigator | One matching registered character among two players; Librarian can receive zero Outsiders. Washerwoman can be its own match when the only Townsfolk. |
| Chef | Count adjacent evil pairs around the complete seating circle, including the closing edge. |
| Empath | Count the two closest living neighbours, skipping dead seats. |
| Fortune Teller | Test the chosen pair for a registered Demon or the setup good-player red herring. |
| Undertaker | Learn the registered character of the player who died by execution that day. |
| Monk | Protect another chosen player from Demon effects that night. |
| Ravenkeeper | Choose a player and learn their registered character after dying at night. |
| Virgin | First nomination is consumed even while poisoned; a functioning Virgin immediately executes a registered Townsfolk nominator and ends the day. |
| Slayer | One real shot during daytime; kill a registered Demon, subject to drunkenness/poisoning. Any player can publicly claim a shot. |
| Soldier | A functioning Soldier cannot be killed by the Demon, including a redirected Mayor death. |
| Mayor | Configurable night redirection; good wins with exactly three alive and no execution. An execution of a dead player still prevents this win. |
| Butler | Choose another player nightly. While alive, follow the master restriction even if unknowingly poisoned; the legal-action menu must not reveal poisoning. A dead Butler has no such restriction. |
| Drunk | Receives a displayed unused Townsfolk role and takes its choices, but has no actual Townsfolk ability; storyteller information can be false. |
| Recluse / Spy | Configurable registration, including while dead; poisoning disables misregistration. Spy additionally receives the Grimoire nightly. |
| Saint | Evil wins on death by execution while functioning; poisoning disables this. |
| Poisoner | Chosen player is poisoned through the next day while the source ability remains active. |
| Baron | Replace two Townsfolk with two Outsiders during setup. |
| Scarlet Woman | Become the Imp when it dies with at least five alive immediately before death, if the Scarlet Woman is functioning. Takes priority over an Imp's ordinary successor choice. |
| Imp | Choose any player, including self or a dead player, after the first night; self-kill passes to a living Minion. |

## Legal choices and voting

The engine generates the available action objects and checks an exact match before advancing. Player text and private notes have bounded lengths. Ability choices can target dead players unless the ability excludes them, and Monk/Butler cannot choose themselves. Two-target Fortune Teller choices contain distinct players.

Only living players nominate, once per day. A player can be nominated once per day, including a dead player. Votes require at least half the living players (rounded up). A strictly higher tally replaces the block; an equal highest tally clears it without resetting the high watermark. Living players may vote on each nomination; dead players may spend one vote for the remainder of the game. Nomination voting uses a simultaneous raised-hands model: other intentions are collected before the Butler is asked, allowing its master restriction to be enforced without exposing role identity publicly. The poisoned Butler still follows the apparent restriction; the simulator does not grant knowledge of its poisoning through the action menu. The resulting votes are public.

## Explicit simulation pacing

The local runner provides a configurable number of conversation rounds, where each player may speak, whisper to one player, claim a Slayer shot or pass. Whisper participants receive the text; it is absent from all other views. With zero conversation rounds, a separate day-ability opportunity still allows Slayer shots. Nomination passes are offered again after new nominations until everyone passes or all legal nominations are consumed. Virgin executions end the day immediately. This turn-based pacing replaces real-world free-form simultaneous speech; conversation and runtime limits are simulator policy, not additional Clocktower victory rules.

The engine decides victories after deaths and at the end of a day. No living Demon gives good victory; otherwise two living players give evil victory. Saint and Mayor supply their stated alternate wins. A configured limit, operator stop, provider failure or restart produces an interruption with no winner.

## Storyteller choices

Choices use a private RNG seeded by the config and are recorded only in omniscient events.

- `misinformation`: seeded random plausible information, or truthful information when possible. Drunk/poisoned players still receive choices and information without being told they are impaired. A poisoned Spy can receive the truthful Grimoire, a legal storyteller choice.
- `registration`: natural identity, always misregister when the requested category permits it, or seeded random. Each relevant registration is chosen independently. Misregistration never actually changes a player's role, team, setup category, Demon succession eligibility or victory condition.
- `mayor_bounce`: never, always or seeded random. A redirected target is chosen from the other players, including dead players; normal Demon protections still apply.
- `imp_successor`: first living eligible Minion clockwise in seat order, or seeded random. A functioning Scarlet Woman with the required living count takes precedence.

This is an explicit mechanical storyteller, not a model pretending to be a human Storyteller. It does not optimize balance dynamically. The script registry separates character metadata and night order; future scripts add their rules handlers and configuration validation without changing provider or UI protocols.
