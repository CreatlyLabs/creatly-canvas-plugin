---
name: film.script.write
description: Create or revise a structured film script proposal.
version: 1.0.0
---

# Film Script Writing

Create or revise only the requested script proposal. Preserve the requested
scene references and format. Each scene must state its heading, location, time,
purpose, action, dialogue, sound cues, and revision notes where relevant.

Use only the supplied message, artifacts, authorized context, and evidence
locks. Do not read an unapproved current state, write to the canvas, submit
generation, decide acceptance, or create Film runtime objects.

For `locked_goal`, follow the locked FilmGoalVersion and script-specific
creative direction. For `ad_hoc`, do not invent or modify a FilmGoal. Return
the exact output shape for `film.script.write@1` and no extra fields.
