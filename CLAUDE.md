# Roads to Secret Wars — POC

Stardew-style Marvel RPG proof of concept. Python 3.11 + pygame-ce.
The build spec is docs/GAME_SPEC.md — read it before any task and follow its
numbers and schemas exactly.

## Commands
- Run: `python -m game`
- Test: `pytest`

## Rules
- Do not make changes beyond the specific task requested. No drive-by
  refactors, renames, or "improvements."
- Game logic stays pure-Python and unit-tested; pygame only in rendering/input.
- All content comes from JSON in /data — never hardcode character or item data.
- All tunable numbers come from game/config.py, sourced from the spec.
- Work one milestone (spec §9) at a time; run pytest before finishing a task.
- Placeholder art = colored rectangles + text. Do not spend effort on art.
