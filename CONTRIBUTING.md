# Contributing to KiCad MCP Integration

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Table of Contents

- [Git Workflow](#git-workflow)
- [Branch Structure](#branch-structure)
- [Commit Guidelines](#commit-guidelines)
- [Development Process](#development-process)
- [Testing Requirements](#testing-requirements)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)

## Git Workflow

This project uses a modified Git Flow workflow with the following branches:

### Branch Structure

```
main (production)
  ↓
develop (integration)
  ↓
feature/* (new features)
bugfix/* (bug fixes)
hotfix/* (urgent fixes for main)
release/* (release preparation)
```

### Main Branches

#### `main`
- **Purpose**: Production-ready code
- **Protection**: Protected, requires PR and reviews
- **Merges from**: `release/*` and `hotfix/*` only
- **Tags**: All releases are tagged (e.g., `v1.0.0`)

#### `develop`
- **Purpose**: Integration branch for features
- **Protection**: Requires PR for merges
- **Merges from**: `feature/*`, `bugfix/*`, `release/*`
- **Status**: Should always be stable

### Supporting Branches

#### `feature/*`
- **Purpose**: Develop new features
- **Naming**: `feature/feature-name`
- **Branch from**: `develop`
- **Merge into**: `develop`
- **Examples**:
  - `feature/auto-routing`
  - `feature/web-ui`
  - `feature/kicad7-support`

#### `bugfix/*`
- **Purpose**: Fix bugs in development
- **Naming**: `bugfix/bug-description`
- **Branch from**: `develop`
- **Merge into**: `develop`
- **Examples**:
  - `bugfix/gerber-export-error`
  - `bugfix/flatpak-permissions`

#### `hotfix/*`
- **Purpose**: Critical fixes for production
- **Naming**: `hotfix/critical-issue`
- **Branch from**: `main`
- **Merge into**: `main` AND `develop`
- **Creates**: New version tag
- **Examples**:
  - `hotfix/security-vulnerability`
  - `hotfix/data-loss-bug`

#### `release/*`
- **Purpose**: Prepare for production release
- **Naming**: `release/v1.1.0`
- **Branch from**: `develop`
- **Merge into**: `main` AND `develop`
- **Activities**: Version bumps, final testing, documentation updates

## Commit Guidelines

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

### Examples

```bash
# Feature
git commit -m "feat: add auto-routing tool

Implements automatic trace routing between components using
pcbnew's routing API.

Closes #42"

# Bug fix
git commit -m "fix: correct Gerber layer export order

Edge.Cuts was being exported before copper layers, causing
issues with some manufacturers.

Fixes #38"

# Documentation
git commit -m "docs: update Flatpak installation instructions

Added troubleshooting section for permission issues."
```

### Commit Best Practices

1. **Atomic commits**: Each commit should represent one logical change
2. **Present tense**: "add feature" not "added feature"
3. **Imperative mood**: "fix bug" not "fixes bug"
4. **Reference issues**: Use "Fixes #123" or "Closes #456"
5. **Include co-authors** when pair programming:
   ```
   Co-Authored-By: Name <email@example.com>
   ```

## Development Process

### Starting a New Feature

```bash
# 1. Update develop branch
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feature/my-new-feature

# 3. Make changes and commit
git add .
git commit -m "feat: implement my new feature"

# 4. Push to remote
git push -u origin feature/my-new-feature

# 5. Create Pull Request on GitHub/GitLab
```

### Fixing a Bug

```bash
# 1. Update develop
git checkout develop
git pull origin develop

# 2. Create bugfix branch
git checkout -b bugfix/fix-gerber-export

# 3. Fix and test
# ... make changes ...
./venv/bin/pytest tests/test_fabrication.py

# 4. Commit and push
git add .
git commit -m "fix: correct Gerber export for Edge.Cuts layer"
git push -u origin bugfix/fix-gerber-export

# 5. Create Pull Request
```

### Creating a Hotfix

```bash
# 1. Branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-security-fix

# 2. Fix the issue
# ... make changes ...

# 3. Test thoroughly
./venv/bin/pytest

# 4. Commit
git add .
git commit -m "fix: patch security vulnerability in file export

Critical security fix for path traversal vulnerability.

Fixes CVE-2024-XXXXX"

# 5. Merge to main
git checkout main
git merge --no-ff hotfix/critical-security-fix

# 6. Tag new version
git tag -a v1.0.1 -m "Hotfix v1.0.1: Security patch"

# 7. Merge back to develop
git checkout develop
git merge --no-ff hotfix/critical-security-fix

# 8. Push everything
git push origin main develop --tags

# 9. Delete hotfix branch
git branch -d hotfix/critical-security-fix
```

### Preparing a Release

```bash
# 1. Create release branch from develop
git checkout develop
git pull origin develop
git checkout -b release/v1.1.0

# 2. Bump version numbers
# Edit pyproject.toml, README.md, etc.

# 3. Update CHANGELOG
# Add release notes

# 4. Final testing
./venv/bin/pytest
# ... all tests ...

# 5. Commit version bump
git add .
git commit -m "chore: bump version to v1.1.0"

# 6. Merge to main
git checkout main
git merge --no-ff release/v1.1.0

# 7. Tag release
git tag -a v1.1.0 -m "Release v1.1.0: Feature summary"

# 8. Merge back to develop
git checkout develop
git merge --no-ff release/v1.1.0

# 9. Push
git push origin main develop --tags

# 10. Clean up
git branch -d release/v1.1.0
```

## Testing Requirements

All contributions must include tests and pass existing tests.

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run unit tests
pytest tests/test_server.py
pytest tests/test_fabrication.py

# Run with KiCad integration
flatpak run --command=python3 --filesystem=host org.kicad.KiCad \
  tests/manual_test_server_real.py
```

### Test Coverage

- New features: Must include tests
- Bug fixes: Must include regression tests
- Minimum coverage: 40%; increases should be accompanied by stable tests

## Code Style

### Python Style Guide

Follow PEP 8 with these guidelines:

```python
# Good
async def export_gerber(self, output_dir: str, layers: Optional[List[str]] = None) -> Dict:
    """
    Export Gerber files for PCB fabrication.

    Args:
        output_dir: Output directory path
        layers: List of layers to export (default: all standard layers)

    Returns:
        Dict with status and list of generated files
    """
    pass

# Bad
def exportGerber(output_dir,layers=None):
    pass
```

### Best Practices

1. **Type hints**: Use everywhere
2. **Docstrings**: Document all public functions
3. **Error handling**: Always handle exceptions gracefully
4. **Logging**: Use logging, not print statements (except CLI tools)
5. **Constants**: Use UPPERCASE for constants
6. **Line length**: Max 100 characters (prefer 88 for Black compatibility)

### Checking Code Style

```bash
# Install development dependencies
pip install black flake8 mypy

# Format code
black *.py

# Check style
flake8 *.py

# Type checking
mypy *.py
```

## Pull Request Process

### Before Creating a PR

1. ✅ All tests pass
2. ✅ Code follows style guide
3. ✅ Documentation updated
4. ✅ CHANGELOG updated (if applicable)
5. ✅ Commit messages follow guidelines
6. ✅ Branch is up-to-date with target branch

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added for new features
- [ ] Tested with real KiCad project
- [ ] Tested in Flatpak environment

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Tests added/updated

## Related Issues
Fixes #(issue number)

## Screenshots (if applicable)
```

### Review Process

1. **Automated checks**: Must pass CI/CD (when available)
2. **Code review**: At least one approval required
3. **Testing**: Reviewer tests changes locally
4. **Documentation**: Reviewer verifies docs are updated
5. **Merge**: Squash small commits, preserve history for features

### After Merge

1. Delete feature branch (if not needed)
2. Update local branches:
   ```bash
   git checkout develop
   git pull origin develop
   ```
3. Close related issues

## Development Setup

### First Time Setup

```bash
# Clone repository
git clone <repository-url>
cd MCP-KiCad

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install package and development dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
nano .env  # Add ANTHROPIC_API_KEY

# Run tests
pytest

# Setup Flatpak (optional)
./kicad_flatpak_setup.sh
```

### Development Environment

Recommended tools:
- **Python**: 3.10+
- **KiCad**: 9.0+ (Flatpak or native)
- **Git**: 2.30+
- **Editor**: VS Code, PyCharm, or similar
- **Virtual environment**: Always use venv

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes (v2.0.0)
- **MINOR**: New features, backward compatible (v1.1.0)
- **PATCH**: Bug fixes, backward compatible (v1.0.1)

### Version Tags

All releases are tagged:
```bash
v1.0.0  # Initial release
v1.1.0  # New features
v1.1.1  # Bug fixes
v2.0.0  # Breaking changes
```

## Communication

- **Issues**: Use GitHub Issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Email**: For security issues, email maintainers directly

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Questions?

If you have questions:
1. Check existing documentation
2. Search closed issues
3. Ask in GitHub Discussions
4. Open a new issue with the "question" label

---

**Thank you for contributing!** 🎉

Your contributions help make KiCad MCP Integration better for everyone.
