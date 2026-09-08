---
name: gsd-workflow
description: >-
  Executes the Get Shit Done (GSD) spec-driven development workflow. Use when tackling complex tasks that benefit from structured research, planning, fresh context execution, and systematic verification to avoid context rot.
---

# Get Shit Done (GSD) Workflow Skill

Use this skill to guide execution through the 4 GSD phases:

## Phase 1: Research & Discovery (`/gsd:research`)
1. Analyze requirements and read relevant codebase files.
2. Identify dependencies, affected components, and potential side effects.
3. Formulate research findings and explicitly identify any unknowns.

## Phase 2: Spec & Plan (`/gsd:plan`)
1. Define atomic implementation steps.
2. Outline specific verification checks for each step (unit tests, manual checks, linting).
3. Document expected inputs and outputs cleanly.

## Phase 3: Execution (`/gsd:execute`)
1. Execute one planned atomic step at a time.
2. Keep context lean—do not output excessive diagnostic logs to context.
3. Immediately fix any syntax or immediate runtime errors before proceeding.

## Phase 4: Verification (`/gsd:verify`)
1. Run automated build and test commands.
2. Verify all acceptance criteria established in Phase 2.
3. Summarize completed work and clean up scratch files.
