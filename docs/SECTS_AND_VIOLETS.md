# Sects & Violets: supported example roster

This first implementation supports a fixed, legal ten-player setup, with assignments shuffled by the setup seed:

- Seven Townsfolk: Clockmaker, Dreamer, Flowergirl, Town Crier, Oracle, Seamstress, Sage.
- Two Minions: Evil Twin, Witch.
- One Demon: Vortox.

`examples/sects-and-violets.json` alternates five GPT-5.6 Luna and five GPT-6 Luna players, with independent personas. Both use Codex, low reasoning, and fast service. Those are the lowest reasoning effort and fastest service tier advertised for these models by the local Codex catalog when the example was prepared. The total token cap is disabled; turn, day, context, and runtime limits still apply.

The full 25-character script appears in the reference and can supply bluffs or Dreamer information. Only the ten characters above have implemented abilities. Configuration rejects other Sects & Violets setups; the app does not simulate unimplemented characters as if they had no ability. Role-changing characters, madness, other Demons, and Outsiders are not supported yet.

## Rules implemented

The [official script](https://wiki.bloodontheclocktower.com/Sects_%26_Violets) and character pages define the rules:

- [Clockmaker](https://wiki.bloodontheclocktower.com/Clockmaker) measures the shorter circular seating distance from Demon to nearest Minion on the first night.
- [Dreamer](https://wiki.bloodontheclocktower.com/Dreamer) chooses another player and receives one good and one evil character. With an active Vortox, both characters are wrong.
- [Flowergirl](https://wiki.bloodontheclocktower.com/Flowergirl) checks whether a Demon voted during the preceding day, while [Town Crier](https://wiki.bloodontheclocktower.com/Town_Crier) checks Minion nominations. A nomination still counts if its nominator dies to the Witch.
- [Oracle](https://wiki.bloodontheclocktower.com/Oracle) counts dead evil players after that night's Demon attack.
- [Seamstress](https://wiki.bloodontheclocktower.com/Seamstress) can defer using their ability and then choose two different other players, living or dead, once per game.
- [Sage](https://wiki.bloodontheclocktower.com/Sage) receives a pair only when killed by the Demon. The pair includes their killer normally, and excludes Demons under an active Vortox.
- [Witch](https://wiki.bloodontheclocktower.com/Witch) curses a player for the next day. Their nomination causes immediate death but continues to a vote. The curse ceases when only three players live or the Witch loses their ability.
- [Evil Twin](https://wiki.bloodontheclocktower.com/Evil_Twin) and their chosen good counterpart privately learn each other's identities and characters. While both live and the ability works, good cannot win even after the Demon dies. Executing the good counterpart, including an already-dead counterpart, loses for good while the Evil Twin's ability works.
- [Vortox](https://wiki.bloodontheclocktower.com/Vortox) attacks starting on night two and forces Townsfolk ability information to be false, including when the Townsfolk is impaired. Role notifications, evil-team setup information, and Twin information are unaffected. A day with no execution loses for good while the Vortox is active; executing a dead player counts as an execution, but a Witch death does not.

Storyteller selections, false numbers, Dreamer alternatives, and Sage pairs use the seeded private RNG and appear only in the full audit record. Resuming reconstructs the generator and RNG from recorded actions and verifies the event history before calling models again.
