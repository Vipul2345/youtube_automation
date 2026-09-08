# Ralph Loop Autonomous Iteration Rules

## Core Principles
1. **Continuous Goal Convergence**: Execute sub-task iterations continuously until all target requirements and automated tests pass cleanly.
2. **Fresh Context Strategy**: Treat each iteration cycle as a clean execution step, persisting state via `.ralph_state.json` and `progress.txt` rather than keeping bloated context memory.
3. **Empirical Verification**: Never exit an iterative loop without clean automated test output or verifiable proof of success.

## Loop Rules & Safety Safeguards
- **Max Iteration Limit**: Default maximum iterations per task run is 10 cycles to avoid runaway loops or infinite retries.
- **State File**: Maintain task progress in `.ralph_state.json` or scratch artifacts (`step`, `status`, `last_error`, `passing_tests`).
- **No Premature Exit**: Do not stop early when minor non-critical tests fail; fix them within the loop before declaring completion.
