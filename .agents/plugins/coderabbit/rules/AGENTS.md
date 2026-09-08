# CodeRabbit Code Review & Quality Rules

## Review Standards
When performing a CodeRabbit AI review, evaluate code across 5 core dimensions:

1. **Correctness & Logic**: Verify business logic correctness, edge cases, error handling, null/undefined safety, and resource leaks.
2. **Security & Vulnerabilities**: Audit input sanitization, authentication, authorization, secret exposure, and dependency vulnerabilities.
3. **Performance & Efficiency**: Identify redundant operations, unoptimized queries, memory leaks, and unnecessary allocations.
4. **Maintainability & Readability**: Enforce clean code principles, clear naming conventions, proper modularization, and docstrings.
5. **Test Coverage**: Ensure high-risk paths, new functions, and bug fixes have corresponding automated unit/integration tests.

## Feedback Formatting Rules
- Categorize findings by severity: `[CRITICAL]`, `[HIGH]`, `[MEDIUM]`, `[LOW]`, `[INFO]`.
- Provide exact line references (`file.ext#L10-L15`) and concrete code suggestion diffs for fixes.
