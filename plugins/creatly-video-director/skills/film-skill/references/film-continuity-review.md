---
name: film.continuity.review
description: Review film continuity and report evidence-backed issues without formal approval.
version: 1.0.0
---

# Film Continuity Review

Produce only a continuity report for the requested scope, targets, and
dimensions. Separate evidence-backed issues from passed checks. Every issue
must name its severity, dimension, affected targets, evidence, description,
and a practical recommendation.

Do not read, create or modify a formal review, accept output,
write project state, submit generation, or create runtime workflow objects.

For `locked_goal`, follow the locked FilmGoalVersion and continuity-specific
creative direction. For `ad_hoc`, do not invent or modify a FilmGoal. Return
the exact output shape for `film.continuity.review@1` and no extra fields.
