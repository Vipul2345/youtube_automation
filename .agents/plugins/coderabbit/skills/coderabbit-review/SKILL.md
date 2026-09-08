---
name: coderabbit-review
description: >-
  Executes an AI-powered CodeRabbit review over git diffs, changed files, or specific repository modules. Generates structured audit reports with severity ratings and actionable code fixes.
---

# CodeRabbit Review Skill

Use this skill to perform automated code reviews:

## Execution Steps
1. **Identify Review Scope**: Determine target files, git diff (`git diff HEAD~1`), or specific pull request files.
2. **Multi-Pass Inspection**:
   - Pass 1: Correctness & Logic check
   - Pass 2: Security & Secret Audit
   - Pass 3: Performance & Resource usage
   - Pass 4: Code Style & Maintainability
3. **Generate Review Report**:
   - Include Executive Summary of findings.
   - List categorized issues with file links and suggested replacement code diffs.
   - Provide overall approval / request changes status recommendation.
