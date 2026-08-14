# Open Source Quick Start Checklist

This is a condensed, actionable checklist derived from the comprehensive [OPEN_SOURCE_PLAN.md](OPEN_SOURCE_PLAN.md). Use this for tracking progress.

## 🚨 CRITICAL - Must Complete Before Going Public

```
[ ] 1. Scan git history for secrets
    Command: git log --all -p | grep -iE '(api[_-]?key|secret|password|xoxb-|xapp-|sk-ant-)' | head -50
    
[ ] 2. Create LICENSE file (MIT)
    Copy from: https://opensource.org/licenses/MIT
    
[ ] 3. Remove personal information
    Files: README.md, plans/*.md, src/benedict/workspace/workspace_manager.py,
           src/benedict/agent.py, src/benedict/commands/command_definitions.py
    Replace: mkarots → example-org, @michael → @alice
    
[ ] 4. Create SECURITY.md
    Include: How to report vulnerabilities, supported versions
    
[ ] 5. Create CODE_OF_CONDUCT.md
    Use: Contributor Covenant v2.1 (https://www.contributor-covenant.org/)
    
[ ] 6. Create CONTRIBUTING.md
    Include: Setup, development workflow, PR guidelines, code style
    
[ ] 7. Create GitHub issue templates
    - .github/ISSUE_TEMPLATE/bug_report.md
    - .github/ISSUE_TEMPLATE/feature_request.md
    
[ ] 8. Create GitHub PR template
    - .github/PULL_REQUEST_TEMPLATE.md
    
[ ] 9. Set up basic CI workflow
    - .github/workflows/ci.yml (lint, type check, tests)
    
[ ] 10. Add basic test structure
     Even if tests are minimal, show the framework exists
```

## ⚠️ HIGH PRIORITY - Should Complete Before Launch

```
[ ] 11. Write unit tests for core modules
     Target: >50% coverage
     Priority: agent.py, commands/, workspace/
     
[ ] 12. Add comprehensive type hints
     Tool: mypy
     
[ ] 13. Update README with badges
     - License badge
     - Python version badge
     - CI status badge (once CI is set up)
     
[ ] 14. Set up branch protection rules
     - Require PR reviews
     - Require CI passing
     - No force push to main
     
[ ] 15. Configure Dependabot
     File: .github/dependabot.yml
     
[ ] 16. Add .editorconfig
     Ensures consistent formatting across editors
     
[ ] 17. Add pre-commit hooks
     File: .pre-commit-config.yaml
     Hooks: black, ruff, trailing-whitespace, end-of-file-fixer
     
[ ] 18. Clean up CHANGELOG.md for 1.0 release
     Add section: "v1.0.0 - Open Source Launch"
     
[ ] 19. Update all documentation links
     Change personal URLs to final repository URL
     
[ ] 20. Create MAINTAINERS.md
     List core team and governance structure
```

## 📋 RECOMMENDED - Complete Before Heavy Promotion

```
[ ] 21. Achieve >80% test coverage
     
[ ] 22. Set up GitHub Discussions
     Categories: Q&A, Ideas, Show and Tell
     
[ ] 23. Create release workflow
     File: .github/workflows/release.yml
     
[ ] 24. Prepare PyPI package
     Test with TestPyPI first
     
[ ] 25. Add devcontainer support
     File: .devcontainer/devcontainer.json
     
[ ] 26. Create FAQ section
     Add to README or separate doc
     
[ ] 27. Create demo video/GIF
     Show quick setup and usage
     
[ ] 28. Write launch announcement
     Blog post or detailed README section
     
[ ] 29. Add repository topics
     Topics: slack-bot, ai, llm, python, slack-app, claude, chromadb
     
[ ] 30. Create social preview image
     1200x630px image for social shares
```

## 🎯 Quick Command Reference

### Scan for Secrets
```bash
# Comprehensive secret scan
git log --all --full-history -p | grep -iE 'xoxb-|xapp-|sk-ant-|api[_-]?key.*=.*[a-zA-Z0-9]{20,}'

# Check current files
rg -i 'xoxb-|xapp-|sk-ant-' --no-ignore

# Install and use truffleHog (recommended)
pip install truffleHog
trufflehog filesystem . --json
```

### Set Up Pre-commit
```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml (see template below)

# Install hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

### Run Tests (once created)
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio

# Run tests with coverage
pytest --cov=src/benedict --cov-report=html --cov-report=term

# View coverage report
open htmlcov/index.html
```

### Build and Test Package
```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Check package
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ benedict
```

### Set Up GitHub CLI (for automation)
```bash
# Create issue templates
gh api repos/OWNER/REPO/issues/templates

# Enable discussions
gh api repos/OWNER/REPO --method PATCH -f has_discussions=true

# Add topics
gh api repos/OWNER/REPO --method PUT -f topics='["slack-bot","ai","llm","python"]'
```

## 📝 Template Snippets

### LICENSE (MIT) - First 3 lines
```
MIT License

Copyright (c) 2026 [Your Name or Organization]
...
```

### SECURITY.md - Structure
```markdown
# Security Policy

## Supported Versions
## Reporting a Vulnerability
## Security Best Practices
```

### CODE_OF_CONDUCT.md
```markdown
# Contributor Covenant Code of Conduct

## Our Pledge
...
(Use standard Contributor Covenant text)
```

### .github/workflows/ci.yml - Basic Structure
```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Lint
        run: |
          ruff check .
          black --check .
      - name: Type check
        run: mypy src/
      - name: Test
        run: pytest --cov
```

### .pre-commit-config.yaml
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.15
    hooks:
      - id: ruff
```

## 🚀 Launch Day Checklist

```
2 weeks before:
[ ] All CRITICAL items complete
[ ] All HIGH PRIORITY items complete
[ ] Documentation reviewed
[ ] At least basic tests exist

1 week before:
[ ] Announcement draft ready
[ ] Social media accounts created (if using)
[ ] Community channels set up
[ ] Release tagged and ready

Launch day:
[ ] Make repository public
[ ] Publish first release
[ ] Post announcements (HN, Reddit, Twitter)
[ ] Monitor for immediate issues
[ ] Respond to initial questions

Week 1 after:
[ ] Daily monitoring of issues/discussions
[ ] Quick response to bugs
[ ] Thank early contributors
[ ] Update docs based on feedback
```

## 📊 Progress Tracking

Update this section with dates as you complete milestones:

- [ ] Planning Complete: ____
- [ ] Critical Items Complete: ____
- [ ] High Priority Items Complete: ____
- [ ] Launch Ready: ____
- [ ] Public Launch: ____
- [ ] First External Contribution: ____
- [ ] 10 GitHub Stars: ____
- [ ] 50 GitHub Stars: ____
- [ ] PyPI Published: ____

## 🆘 Blockers & Questions

Use this section to track any blockers or open questions:

1. 
2. 
3. 

---

**Next Steps**: Start with items 1-10 in the CRITICAL section above.

For detailed explanations and context, see [OPEN_SOURCE_PLAN.md](OPEN_SOURCE_PLAN.md).
