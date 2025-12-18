# Contributing to GitLab Hierarchy Extractor

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Issue Guidelines](#issue-guidelines)

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip and virtualenv
- Git
- GitLab account with API access (for testing)

### Development Setup

1. **Fork and Clone**

```bash
# Fork the repository on GitHub/GitLab first, then:
git clone https://github.com/yourusername/neo-extractor.git
cd neo-extractor
```

2. **Create Virtual Environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Development Dependencies**

```bash
pip install -e ".[dev]"
```

This installs the package in editable mode with all development dependencies:
- pytest, pytest-cov (testing)
- black (code formatting)
- flake8 (linting)
- mypy (type checking)
- pre-commit (git hooks)

4. **Install Pre-commit Hooks**

```bash
pre-commit install
```

This sets up automatic checks before each commit:
- Code formatting (black)
- Linting (flake8)
- Type checking (mypy)
- Trailing whitespace removal
- YAML/JSON validation

5. **Configure Environment**

```bash
cp .env.example .env
# Edit .env with your GitLab credentials
```

## Development Workflow

### Branch Strategy

- `main` - stable releases
- `develop` - integration branch for features
- `feature/xyz` - new features
- `bugfix/xyz` - bug fixes
- `docs/xyz` - documentation updates

### Creating a Feature Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

### Making Changes

1. **Write Code**
   - Follow [PEP 8](https://pep8.org/) style guide
   - Add docstrings to functions and classes
   - Keep functions small and focused
   - Use type hints where appropriate

2. **Write Tests**
   - Add unit tests for new functionality
   - Maintain or improve test coverage
   - Test edge cases and error conditions

3. **Update Documentation**
   - Update README.md if needed
   - Add docstrings to new code
   - Update ARCHITECTURE.md for design changes
   - Add examples if appropriate

4. **Commit Changes**

```bash
git add .
git commit -m "feat: add new feature"
```

Use conventional commit messages:
- `feat:` - new feature
- `fix:` - bug fix
- `docs:` - documentation changes
- `test:` - test additions/changes
- `refactor:` - code refactoring
- `style:` - formatting changes
- `chore:` - maintenance tasks

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_database.py

# Run with coverage report
pytest --cov=gitlab_hierarchy --cov-report=html

# Run specific test
pytest tests/test_database.py::test_database_initialization

# Run with verbose output
pytest -v

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Writing Tests

#### Unit Test Example

```python
import pytest
from gitlab_hierarchy.label_parser import LabelParser


def test_parse_labels():
    """Test label parsing functionality."""
    parser = LabelParser()
    labels = ['priority:high', 'type:bug']

    result = parser.parse_labels(labels)

    assert result['label_priority'] == 'high'
    assert result['label_type'] == 'bug'
```

#### Integration Test Example

```python
import pytest
from gitlab_hierarchy import HierarchyExtractor


@pytest.mark.integration
def test_extract_hierarchy(temp_db, mock_gitlab_client):
    """Test complete extraction workflow."""
    extractor = HierarchyExtractor(
        gitlab_url='https://gitlab.example.com',
        db_path=temp_db
    )

    stats = extractor.extract(group_id=123, epic_iid=1)

    assert stats['total_items'] > 0
```

### Test Coverage

- Aim for 80% minimum coverage
- Focus on critical paths and business logic
- Don't test trivial code (getters, setters)
- Mock external dependencies (GitLab API)

## Code Style

### Formatting with Black

```bash
# Format all files
black .

# Check formatting without changes
black --check .

# Format specific file
black gitlab_hierarchy/database.py
```

**Black configuration** (in `pyproject.toml`):
```toml
[tool.black]
line-length = 100
target-version = ['py38']
```

### Linting with Flake8

```bash
# Lint all files
flake8 gitlab_hierarchy tests

# Lint specific file
flake8 gitlab_hierarchy/database.py
```

**Flake8 configuration** (in `.flake8` or `setup.cfg`):
```ini
[flake8]
max-line-length = 100
exclude = .git,__pycache__,venv
ignore = E203, W503
```

### Type Checking with Mypy

```bash
# Type check all files
mypy gitlab_hierarchy

# Type check specific file
mypy gitlab_hierarchy/database.py
```

**Mypy configuration** (in `pyproject.toml`):
```toml
[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### Style Guidelines

#### Docstrings

Use Google-style docstrings:

```python
def extract_hierarchy(group_id: int, epic_iid: int) -> dict:
    """Extract epic hierarchy from GitLab.

    Args:
        group_id: GitLab group ID
        epic_iid: Epic IID within the group

    Returns:
        Dictionary with extraction statistics

    Raises:
        ValueError: If group_id or epic_iid is invalid
        ConnectionError: If GitLab API is unreachable

    Example:
        >>> extractor = HierarchyExtractor(...)
        >>> stats = extractor.extract(123, 10)
        >>> print(stats['total_items'])
        42
    """
    pass
```

#### Type Hints

Use type hints for function signatures:

```python
from typing import List, Dict, Optional

def get_children(parent_id: str) -> List[Dict[str, Any]]:
    """Get all children of a parent item."""
    pass

def get_item(item_id: str, latest_only: bool = True) -> Optional[Dict[str, Any]]:
    """Get single item by ID."""
    pass
```

#### Naming Conventions

- **Functions/methods**: `lowercase_with_underscores`
- **Classes**: `PascalCase`
- **Constants**: `UPPERCASE_WITH_UNDERSCORES`
- **Private members**: `_leading_underscore`
- **Module-level private**: `_single_leading_underscore`

## Submitting Changes

### Pull Request Process

1. **Update Your Branch**

```bash
git checkout develop
git pull origin develop
git checkout feature/your-feature
git rebase develop
```

2. **Run All Checks**

```bash
# Format code
black .

# Run linter
flake8 gitlab_hierarchy tests

# Type check
mypy gitlab_hierarchy

# Run tests
pytest

# Check coverage
pytest --cov=gitlab_hierarchy --cov-report=term-missing
```

3. **Push to Your Fork**

```bash
git push origin feature/your-feature
```

4. **Create Pull Request**

- Go to GitHub/GitLab
- Click "New Pull Request"
- Select `develop` as base branch
- Fill in PR template:
  - Description of changes
  - Related issue(s)
  - Testing done
  - Screenshots (if UI changes)

5. **Address Review Comments**

- Make requested changes
- Push new commits to same branch
- PR will update automatically

### Pull Request Checklist

Before submitting, ensure:

- [ ] Code follows style guidelines (black, flake8, mypy pass)
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Commit messages follow conventional format
- [ ] No merge conflicts with develop
- [ ] PR description is clear and complete
- [ ] All CI checks pass

## Issue Guidelines

### Reporting Bugs

Use the bug report template and include:

- **Description**: Clear description of the bug
- **Steps to Reproduce**: Minimal steps to reproduce
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, Python version, package versions
- **Logs**: Relevant error messages or stack traces

Example:
```markdown
## Description
Extraction fails when epic has circular parent reference

## Steps to Reproduce
1. Create epic A with parent epic B
2. Create epic B with parent epic A
3. Run: `neo extract --group-id 123 --epic-iid 1`

## Expected Behavior
Should detect cycle and skip or warn

## Actual Behavior
Infinite loop until max depth reached

## Environment
- OS: Ubuntu 20.04
- Python: 3.9.7
- neo: 1.0.0

## Logs
```
[stack trace here]
```
```

### Requesting Features

Use the feature request template and include:

- **Problem**: What problem does this solve?
- **Proposed Solution**: How would you solve it?
- **Alternatives**: Other solutions considered
- **Use Cases**: Real-world examples
- **Additional Context**: Mockups, examples, references

### Asking Questions

Use the question template and include:

- **Question**: Clear, specific question
- **Context**: What are you trying to do?
- **Attempted Solutions**: What have you tried?
- **References**: Links to docs you've checked

## Development Tips

### Debugging

**Enable verbose logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Use pdb for debugging:**
```python
import pdb; pdb.set_trace()
```

**Use pytest with pdb:**
```bash
pytest --pdb  # Drop into debugger on failure
pytest -x --pdb  # Stop at first failure
```

### Testing Against Real GitLab

```bash
# Set up test environment
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="your-token"
export GROUP_ID="123"
export EPIC_IID="10"

# Run manual test
python examples/extract_hierarchy.py

# Check results
sqlite3 hierarchy.db "SELECT * FROM gitlab_hierarchy LIMIT 5"
```

### Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
extractor.extract(group_id=123, epic_iid=1)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

## Getting Help

- **Documentation**: Check [README.md](README.md) and [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Issues**: Search existing issues first
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainers for sensitive issues

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards others

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in commit history

Thank you for contributing! 🎉
