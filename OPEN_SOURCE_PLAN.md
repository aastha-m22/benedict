# Open Source Plan for Benedict

## Executive Summary

This document outlines the complete process for open sourcing the Benedict repository - a Slack bot that provides intelligent, repo-scoped AI agent conversations. The plan covers security review, documentation, licensing, community guidelines, CI/CD setup, and launch strategy.

**Current Status**: Private repository at `mkarots/benedict`
**Target Status**: Public open source project with MIT License
**Estimated Effort**: 15-20 implementation steps across multiple categories

---

## 1. Pre-Release Security Review

### 1.1 Credential Audit
**Status**: ✅ GOOD - No hardcoded credentials found

- [x] All API keys use environment variables
- [x] `.env` files properly excluded in `.gitignore`
- [x] Token handling follows security best practices
- [ ] **Action**: Review git history for accidentally committed secrets
- [ ] **Action**: Consider using `git-secrets` or `truffleHog` to scan history

**Commands to run**:
```bash
# Scan for secrets in git history
git log --all --full-history --source -- '**/\.env*'
git log --all -p | grep -i 'api[_-]key\|secret\|token' | head -20
```

### 1.2 Personal Information Removal
**Status**: ⚠️ NEEDS CLEANUP

**Found references**:
- Username `mkarots` in examples and comments
- Name `@michael` in README examples
- Repository examples using `mkarots/benedict`

**Actions Required**:
- [ ] Replace `mkarots` references with generic examples (`example-org`, `your-org`)
- [ ] Replace `@michael` with `@alice` or `@user`
- [ ] Update example repository names to be generic
- [ ] Review all markdown files for personal details

**Files to update**:
- `README.md` (line 186)
- `plans/slack-agent-architecture.md` (line 148)
- `plans/implementation-plan.md` (line 131)
- `src/benedict/workspace/workspace_manager.py` (line 102)
- `src/benedict/agent.py` (line 219)
- `src/benedict/commands/command_definitions.py` (line 76)

### 1.3 Git History Review
**Status**: PENDING

- [ ] Review commit messages for sensitive information
- [ ] Check for any large binary files that should be removed
- [ ] Consider using `git filter-repo` if history cleanup needed
- [ ] Review PR #1 contents

---

## 2. Legal & Licensing

### 2.1 Create LICENSE File
**Status**: ❌ MISSING

**Action**: Create `LICENSE` file with MIT License text
- README claims MIT License but file doesn't exist
- MIT is appropriate for this type of project
- Include copyright holder and year

**Template**:
```
MIT License

Copyright (c) 2026 [Copyright Holder Name]

Permission is hereby granted, free of charge, to any person obtaining a copy...
```

### 2.2 Add License Headers
**Status**: OPTIONAL

**Consideration**: Add SPDX license identifiers to Python files
```python
# SPDX-License-Identifier: MIT
```

### 2.3 Third-Party Dependencies Review
**Status**: NEEDS REVIEW

**Action**: Review all dependencies in `pyproject.toml` for license compatibility
- [ ] Document all dependency licenses
- [ ] Ensure all are MIT-compatible
- [ ] Add NOTICE file if any dependencies require attribution

**Current dependencies**:
- slack-bolt
- python-dotenv
- anthropic
- sentence-transformers
- chromadb
- pyyaml
- rich

---

## 3. Documentation Enhancements

### 3.1 Core Documentation Files

#### README.md
**Status**: ✅ EXCELLENT - Well structured

**Minor enhancements needed**:
- [ ] Add badges (license, Python version, build status)
- [ ] Add contributing section linking to CONTRIBUTING.md
- [ ] Add code of conduct reference
- [ ] Add security policy reference
- [ ] Update repository URLs from personal to org/project
- [ ] Add "Star us on GitHub" call-to-action

#### CONTRIBUTING.md
**Status**: ❌ MISSING

**Action**: Create comprehensive contributing guide
- [ ] How to set up development environment
- [ ] How to run tests (once tests exist)
- [ ] Code style guidelines (Black, Ruff, Pylint)
- [ ] PR process and expectations
- [ ] Issue reporting guidelines
- [ ] Development workflow
- [ ] Commit message conventions

#### CODE_OF_CONDUCT.md
**Status**: ❌ MISSING

**Action**: Adopt standard code of conduct
- [ ] Use Contributor Covenant (industry standard)
- [ ] Define enforcement procedures
- [ ] Specify contact methods for reporting

#### SECURITY.md
**Status**: ❌ MISSING

**Action**: Create security policy
- [ ] Supported versions
- [ ] How to report vulnerabilities (private disclosure)
- [ ] Security best practices for users
- [ ] Response timeline expectations

### 3.2 Project Governance

#### MAINTAINERS.md
**Status**: ❌ MISSING

**Action**: Define maintainers and governance
- [ ] List core maintainers and roles
- [ ] Define decision-making process
- [ ] Explain how to become a maintainer

### 3.3 User Documentation

**Current status**: ✅ GOOD
- Excellent README with setup instructions
- Detailed SLACK_SETUP.md guide
- Comprehensive architecture documentation
- Good inline code documentation

**Enhancements**:
- [ ] Add FAQ section
- [ ] Create troubleshooting guide (expand existing section)
- [ ] Add video demo/tutorial (optional but valuable)
- [ ] Create CHANGELOG formatting guidelines

---

## 4. Code Quality & Testing

### 4.1 Test Suite
**Status**: ❌ CRITICAL - No tests exist

**Action**: Create comprehensive test suite
- [ ] Unit tests for all modules
- [ ] Integration tests for key flows
- [ ] Mock tests for external dependencies (Slack, Anthropic)
- [ ] Test fixtures and factories
- [ ] Achieve >80% code coverage target

**Priority test areas**:
1. Command parsing and classification
2. Conversation management
3. Workspace management
4. Context building
5. Semantic indexing
6. Repository reading

**Test structure**:
```
tests/
├── unit/
│   ├── test_agent.py
│   ├── test_commands/
│   ├── test_workspace/
│   ├── test_metadata/
│   └── test_utils/
├── integration/
│   ├── test_slack_integration.py
│   ├── test_llm_integration.py
│   └── test_semantic_search.py
└── conftest.py  # Shared fixtures
```

### 4.2 Code Quality Tools
**Status**: ✅ GOOD - Tools defined in pyproject.toml

**Actions**:
- [ ] Configure pre-commit hooks
- [ ] Add ruff configuration
- [ ] Add mypy for type checking
- [ ] Document code quality standards

### 4.3 Type Hints
**Status**: ⚠️ PARTIAL

**Action**: Add comprehensive type hints
- [ ] Add type hints to all function signatures
- [ ] Use Protocol types consistently
- [ ] Enable mypy strict mode
- [ ] Add py.typed marker for library distribution

---

## 5. CI/CD & Automation

### 5.1 GitHub Actions Workflows
**Status**: ❌ MISSING

**Actions**: Create workflows for:

#### A. Continuous Integration (.github/workflows/ci.yml)
```yaml
- Lint (ruff, black, pylint)
- Type check (mypy)
- Tests (pytest with coverage)
- Security scan (bandit)
- Run on: push, PR
- Test on: Python 3.10, 3.11, 3.12
```

#### B. Release Workflow (.github/workflows/release.yml)
```yaml
- Build package
- Publish to PyPI
- Create GitHub release
- Generate changelog
- Trigger on: version tag (v*)
```

#### C. Documentation (.github/workflows/docs.yml)
```yaml
- Build documentation
- Deploy to GitHub Pages (if applicable)
- Check for broken links
```

### 5.2 GitHub Repository Settings

#### Branch Protection
**Actions**:
- [ ] Protect `main` branch
- [ ] Require PR reviews (1-2 reviewers)
- [ ] Require CI checks to pass
- [ ] Require up-to-date branches
- [ ] No force pushes
- [ ] No deletions

#### GitHub Features
- [ ] Enable Issues
- [ ] Enable Discussions (community Q&A)
- [ ] Enable Projects (for roadmap)
- [ ] Enable Wiki (optional)
- [ ] Set repository topics/tags (python, slack-bot, ai, llm, etc.)

### 5.3 Issue & PR Templates
**Status**: ❌ MISSING

**Actions**: Create templates

#### .github/ISSUE_TEMPLATE/bug_report.md
- [ ] Bug description
- [ ] Steps to reproduce
- [ ] Expected vs actual behavior
- [ ] Environment details
- [ ] Logs/screenshots

#### .github/ISSUE_TEMPLATE/feature_request.md
- [ ] Feature description
- [ ] Use case
- [ ] Proposed solution
- [ ] Alternatives considered

#### .github/PULL_REQUEST_TEMPLATE.md
- [ ] Description of changes
- [ ] Related issues
- [ ] Type of change (bug fix, feature, docs, etc.)
- [ ] Testing done
- [ ] Checklist (tests, docs, changelog)

---

## 6. Release Preparation

### 6.1 Version Management
**Current**: v0.3.17 (from pyproject.toml)

**Actions**:
- [ ] Decide on 1.0.0-rc1 or continue with 0.x series
- [ ] Document versioning scheme (SemVer)
- [ ] Create release procedure documentation
- [ ] Tag initial open source release

**Recommendation**: Release as `v0.4.0` (open source edition)

### 6.2 PyPI Publication
**Status**: PENDING

**Actions**:
- [ ] Register package name on PyPI
- [ ] Verify package builds correctly (`python -m build`)
- [ ] Test package installation from TestPyPI
- [ ] Create PyPI API token
- [ ] Document release process
- [ ] Add PyPI badge to README

### 6.3 CHANGELOG.md
**Status**: ✅ EXISTS - Well maintained

**Actions**:
- [ ] Add section for open source launch
- [ ] Ensure all recent changes documented
- [ ] Follow Keep a Changelog format
- [ ] Link to semantic versioning

---

## 7. Community Building

### 7.1 Repository Setup
**Actions**:
- [ ] Add repository description
- [ ] Add website URL (if applicable)
- [ ] Add topics: `slack-bot`, `ai`, `llm`, `python`, `slack-app`, `claude`, `semantic-search`
- [ ] Create organization (optional) vs personal repo
- [ ] Add social media preview image

### 7.2 Communication Channels
**Actions**:
- [ ] Set up GitHub Discussions
- [ ] Create Discord/Slack community (optional)
- [ ] Set up mailing list (optional)
- [ ] Create Twitter/X account for announcements (optional)

### 7.3 Initial Promotion
**Channels**:
- [ ] Hacker News "Show HN"
- [ ] Reddit (r/Python, r/slack, r/artificialintelligence)
- [ ] Twitter/X announcement
- [ ] Dev.to blog post
- [ ] Product Hunt launch (optional)
- [ ] LinkedIn announcement

---

## 8. Dependency & Infrastructure

### 8.1 External Services
**Current dependencies**:
- Slack API (user-provided tokens)
- Anthropic API (user-provided key)
- No external infrastructure needed

**Actions**:
- [ ] Document all external service requirements
- [ ] Provide clear setup instructions
- [ ] Document API costs
- [ ] Provide mock implementations for testing

### 8.2 Development Tools
**Actions**:
- [ ] Add .editorconfig for consistent formatting
- [ ] Add .pre-commit-config.yaml
- [ ] Document required tools in CONTRIBUTING.md
- [ ] Add devcontainer configuration (optional)

---

## 9. Security & Privacy

### 9.1 Security Scanning
**Actions**:
- [ ] Set up Dependabot for dependency updates
- [ ] Set up CodeQL scanning
- [ ] Add bandit security linter to CI
- [ ] Document security best practices

### 9.2 Data Privacy
**Current**: ✅ GOOD - No data collection

**Document**:
- [ ] Clarify that bot runs locally
- [ ] No telemetry or data collection
- [ ] All data stays in user's environment
- [ ] Slack/Anthropic data handling per their policies

---

## 10. Legal Compliance

### 10.1 Export Compliance
**Actions**:
- [ ] Review export control regulations (encryption, AI)
- [ ] Add appropriate notices if needed
- [ ] Document any usage restrictions

### 10.2 Trademark
**Actions**:
- [ ] Ensure "Benedict" name doesn't infringe
- [ ] Consider registering trademark (optional)
- [ ] Add trademark usage guidelines

---

## Implementation Checklist

### Phase 1: Critical Pre-Release (Must Complete)
- [ ] Create LICENSE file
- [ ] Remove personal information from code/docs
- [ ] Scan git history for secrets
- [ ] Create CONTRIBUTING.md
- [ ] Create CODE_OF_CONDUCT.md
- [ ] Create SECURITY.md
- [ ] Set up basic CI workflow
- [ ] Create issue/PR templates
- [ ] Add test framework structure (even if minimal)
- [ ] Review and update README

### Phase 2: Quality Improvements (Should Complete)
- [ ] Write core unit tests (>50% coverage)
- [ ] Add type hints
- [ ] Set up branch protection
- [ ] Configure pre-commit hooks
- [ ] Add badges to README
- [ ] Create release workflow
- [ ] Document release process
- [ ] Prepare PyPI package

### Phase 3: Community Building (Nice to Have)
- [ ] Set up GitHub Discussions
- [ ] Create demo video
- [ ] Write launch blog post
- [ ] Create social media presence
- [ ] Add comprehensive integration tests
- [ ] Reach >80% test coverage
- [ ] Set up documentation site

---

## Timeline Considerations

### Pre-Launch (Essential Work)
Core files: LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY
Code cleanup: Remove personal info, add basic tests
CI/CD: Basic GitHub Actions workflow
Repository setup: Issue templates, branch protection

### Launch Day
- Make repository public
- Publish to PyPI (optional for launch)
- Announcement on primary channels

### Post-Launch (First 30 Days)
- Monitor issues and PRs
- Engage with early contributors
- Document common questions as FAQ
- Improve based on feedback

---

## Risk Assessment

### High Risk
- **Secrets in git history**: MITIGATED - Review needed but .env properly ignored
- **No tests**: HIGH PRIORITY - Blocks confident releases

### Medium Risk
- **Personal info exposure**: Easy to fix
- **Dependency vulnerabilities**: Monitor with Dependabot
- **Breaking changes for early users**: Version carefully

### Low Risk
- **License compliance**: MIT is permissive
- **Name conflicts**: "Benedict" appears available
- **Community management**: Start small, grow organically

---

## Success Metrics

### Short Term (0-3 months)
- GitHub stars: 50+
- Contributors: 3+
- Issues/PRs: 10+
- PyPI downloads: 100+

### Medium Term (3-6 months)
- GitHub stars: 200+
- Contributors: 10+
- Production deployments: 20+
- Test coverage: >80%

### Long Term (6-12 months)
- Active community (discussions, contributions)
- Regular releases
- Growing ecosystem (plugins, integrations)
- Featured in awesome lists

---

## Resources & References

### Essential Reading
- [Open Source Guides](https://opensource.guide/)
- [GitHub's Guide to Open Source](https://github.com/github/opensource.guide)
- [The Architecture of Open Source Applications](https://aosabook.org/)

### Tools
- `git-secrets`: Prevent committing secrets
- `truffleHog`: Find secrets in git history
- `pre-commit`: Git hook framework
- `bandit`: Python security linter

### License Resources
- [Choose a License](https://choosealicense.com/)
- [SPDX License List](https://spdx.org/licenses/)

---

## Appendix: File Creation Templates

See separate sections below for complete templates of:
- LICENSE (MIT)
- CONTRIBUTING.md
- CODE_OF_CONDUCT.md
- SECURITY.md
- GitHub Action workflows
- Issue/PR templates

---

**Document Status**: Draft - Ready for Review
**Last Updated**: 2026-08-14
**Owner**: Project Maintainer
**Review Cycle**: Update before each release milestone
