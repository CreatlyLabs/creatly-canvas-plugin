---
name: film.work-plan.propose
description: Propose a reviewable film work plan from locked project evidence.
version: 1.0.0
---

# Film Work Plan Proposal

Produce only a structured work-plan proposal. Do not create FilmRun, WorkItem,
canvas changes, generation requests, review decisions, or acceptance decisions.

Use the supplied goal context, source message, evidence lock, project targets,
profile catalog, and constraints. Every proposed item must use an available
profile, preserve its version and digest, name its target project when needed,
and reference only reachable inputs. Dependencies must point to other items in
the same proposal and must not form a cycle.

Include each creative item's `task` using the selected profile's task schema
in the output contract. Keep the task specific to that item; do not replace it
with the overall goal or risk notes. Reuse known scene, character and target
references. If required task details are unknown, leave the task absent and
record the question in `openQuestions`; an incomplete plan cannot be adopted
for execution. Tool-command items use `task: null` and an explicit `toolCommand`
with the approved `actionId` and its semantic `input`. Use only the create,
update, delete, or generation-submission actions allowed by the selected
profile. Include only the semantic fields allowed by the output contract and
leave execution metadata to the host. Keep unknown payload details as open
questions and do not present an incomplete plan as executable.

Formal review outcomes reach you only as facts inside the task. Treat them as
evidence, never as permission to continue, and never read a review yourself.

For `locked_goal`, follow the locked FilmGoalVersion and creative direction.
For `ad_hoc`, do not invent or modify a FilmGoal. Return the exact output shape
for `film.work-plan.propose@1` and no extra fields.
