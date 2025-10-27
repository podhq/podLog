# Contributing

Thanks for your interest in improving podlog! We welcome bug reports, feature requests, and pull requests.

## Getting started

1. Fork the repository and create a feature branch.
2. Install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[otlp]
   pip install -r requirements-dev.txt  # if available
   pre-commit install
   ```

3. Run the test suite and lint checks before pushing:

   ```bash
   pytest
   pre-commit run --all-files
   ```

## Pull request guidelines

- Keep commits focused and include tests for new behavior.
- Update documentation (README, USAGE, CONFIG) when public APIs or configuration options change.
- Ensure `pytest` passes and no type errors or lint warnings remain.
- Describe your change clearly in the PR body and reference any relevant issues.

## Code style

- Follow the existing code conventions: type annotations where practical, descriptive names, and docstrings for modules.
- Use `black`, `ruff`, and `isort` via the bundled pre-commit hooks to maintain consistency.
- Avoid catching broad exceptions; prefer precise exception types.

## Reporting issues

Open an issue with a clear description, reproduction steps, and environment details (Python version, OS, podlog version). Include
stack traces or configuration snippets where applicable.
