---
name: roo-mode-orchestrator
description: >-
  Orchestrates Roo Code sub-agent role transitions (Architect, Code, Ask, Debug, Test) and enforces strict operation boundaries.
---

# Roo Mode Orchestrator Skill

Use this skill to switch agent operating modes and enforce boundary constraints.

## Mode Switching Commands
- **Architect**: Use `/mode:architect` to enter system planning phase.
- **Code**: Use `/mode:code` to execute production code modifications.
- **Ask**: Use `/mode:ask` for read-only exploration and user Q&A.
- **Debug**: Use `/mode:debug` for empirical bug investigation and fixing.
- **Test**: Use `/mode:test` for writing unit/integration test suites.

## Orchestration Protocol
1. **Identify Task Goal**: Determine which mode matches the current user request.
2. **Set Boundary Rules**: Adhere strictly to the permissions defined in `rules/AGENTS.md` for that mode.
3. **Transition cleanly**: When switching modes, log the mode switch explicitly (e.g., `Switching to [Code Mode]...`).
