---
name: film.video.prompt.compose
description: Compose video prompts and motion specifications without submitting work.
version: 1.0.0
---

# Film Video Prompt Composition

Compose only the requested video-prompt proposal. Cover every shot reference,
aspect ratio, and duration policy. Each specification must describe the prompt,
motion, performance, camera movement, duration, continuity anchors, negative
prompt, and optional start frame reference.

Do not select a provider, submit generation, estimate or charge credits, write
to the canvas, decide acceptance, or create runtime workflow objects.

For `locked_goal`, follow the locked FilmGoalVersion and video-prompt creative
direction. For `ad_hoc`, do not invent or modify a FilmGoal. Use only supplied
and authorized evidence, and return the exact output shape for
`film.video.prompt.compose@1` with no extra fields.
