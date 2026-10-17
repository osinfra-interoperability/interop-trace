# Contributing

Keep changes focused and reviewable. Discuss larger architectural changes in an
issue before implementation.

## Workflow

1. Create a short-lived branch from the target branch for one feature, fix or
   documentation change.
2. Develop in small increments and run the relevant checks.
3. Rebase on the target branch before opening or updating a pull request. Keep
   history linear; do not merge the target branch into the feature branch.
4. Use the repository pull request template when available. Explain the behavior
   changed, validation performed and any material limitations.
5. Wait for maintainer review and passing CI before merging.

## Setup and validation

See the [developer guide](docs/developer.md) for Poetry setup, offline tests,
pre-commit hooks, generated component tables and documentation checks.
All required CI checks must pass on the latest commit before merging.

## Commit messages

Use lowercase [Conventional Commits](https://www.conventionalcommits.org/):
`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `build:`, `ci:` or `chore:`.
An optional scope can identify the component. Mark breaking changes with `!` or a
`BREAKING CHANGE:` footer. Pull request/squash titles follow the same convention.

## Before review

- Include tests for meaningful behavior changes and update affected documentation.
- Regenerate component tables when registrations change.
- Record scientific assumptions and interoperability limits accurately.
- Exclude secrets, private data and local experiment outputs.
