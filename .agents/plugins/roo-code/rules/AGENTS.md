# Roo Code Operating Modes & Boundary Rules

When operating under the Roo Code plugin, enforce strict role boundaries based on the active mode:

## 1. Architect Mode (`/mode:architect`)
- **Focus**: High-level design, architecture specifications, API contracts, system modeling.
- **Allowed Actions**: Reading files, searching codebase, writing implementation plans and documentation.
- **Restrictions**: Do NOT write production source code files or execute mutation scripts directly.

## 2. Code Mode (`/mode:code`)
- **Focus**: Feature implementation, refactoring, writing production code.
- **Allowed Actions**: Creating and editing source code files, creating unit tests.
- **Restrictions**: Follow existing architecture specifications cleanly without unsolicited architectural refactors.

## 3. Ask Mode (`/mode:ask`)
- **Focus**: Q&A, codebase exploration, explanation of existing logic.
- **Allowed Actions**: Read-only codebase search, file viewing, rendering diagrams or text answers.
- **Restrictions**: Do NOT mutate any files or execute shell commands that alter state.

## 4. Debug Mode (`/mode:debug`)
- **Focus**: Root cause analysis, error log inspection, minimal surgical bug fixing.
- **Allowed Actions**: Log reading, running debug tests, minimal bug fix editing.
- **Restrictions**: Do NOT refactor working code or add unrelated new features.

## 5. Test Mode (`/mode:test`)
- **Focus**: Test suite authoring, test execution, regression testing.
- **Allowed Actions**: Writing test files, running test runners, asserting code coverage.
- **Restrictions**: Modify production code only when fixing a test harness integration issue.
