---
name: ralph-loop-runner
description: >-
  Runs autonomous iterative execution loops (Ralph Wiggum Loop) in Antigravity. Use for long-running or self-healing tasks that require continuous trial, test verification, and state persistence across cycles until completion.
---

# Ralph Loop Runner Skill

Use this skill to initiate and execute an autonomous Ralph Loop cycle:

## Execution Cycle
1. **Initialize State**: Create or update `.ralph_state.json` with target goals, test command, current iteration (0), and max iterations (10).
2. **Execute Attempt**:
   - Apply targeted changes to address current task goal or failing test.
   - Run verification test suite.
3. **Evaluate Result**:
   - If tests pass cleanly and all goals are met: Mark status `SUCCESS` and exit loop.
   - If tests fail: Record failure traceback in state, increment iteration counter, and loop to step 2.
4. **Guardrail Termination**: If `iteration >= max_iterations` without success, pause loop and prompt user with state log.
