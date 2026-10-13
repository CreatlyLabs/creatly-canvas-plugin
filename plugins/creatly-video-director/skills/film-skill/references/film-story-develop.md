---
name: film.story.develop
description: Develop a film story while preserving evidence and creative direction.
version: 1.0.0
---

# Film Story Development

Develop or revise only the requested story proposal. Build a clear premise,
theme, character arcs, dramatic beats, turning points, ending, and open
questions from the supplied evidence.

Use `film.subject.list@1` only when it is available and existing subject facts
are needed. Do not create or edit subjects through this Skill. Do not write to
the canvas, submit generation, decide acceptance, or create runtime workflow
objects.

For `locked_goal`, apply the locked FilmGoalVersion and the story-specific
creative direction. For `ad_hoc`, answer the current request without inventing
or changing a FilmGoal. Keep every source reference reachable and return the
exact output shape for `film.story.develop@1` with no extra fields.
