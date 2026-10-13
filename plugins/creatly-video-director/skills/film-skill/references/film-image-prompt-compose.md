---
name: film.image.prompt.compose
description: Compose image prompts and generation specifications without submitting work.
version: 1.0.0
---

# Film Image Prompt Composition

Compose only the requested image-prompt proposal. Cover every target reference,
render intent, aspect ratio, and variant count. Each specification must contain
a positive prompt, negative prompt, stable reference inputs, and continuity
anchors that preserve the approved character, scene, and storyboard facts.

Do not select a provider, submit generation, estimate or charge credits, write
to the canvas, decide acceptance, or create runtime workflow objects.

For `locked_goal`, follow the locked FilmGoalVersion and image-prompt creative
direction. For `ad_hoc`, do not invent or modify a FilmGoal. Use only supplied
and authorized evidence, and return the exact output shape for
`film.image.prompt.compose@1` with no extra fields.
