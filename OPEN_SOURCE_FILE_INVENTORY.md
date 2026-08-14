# Open Source File Inventory & Actions

This document provides a comprehensive list of all files that need to be created, modified, or reviewed for open sourcing Benedict.

## 📁 Files to CREATE

### Critical - Must create before going public

1. **LICENSE**
   - Type: Plain text
   - Location: `/LICENSE`
   - Content: MIT License text with copyright holder
   - Status: ❌ Missing

2. **SECURITY.md**
   - Type: Markdown
   - Location: `/SECURITY.md`
   - Content: Vulnerability reporting, supported versions
   - Status: ❌ Missing

3. **CODE_OF_CONDUCT.md**
   - Type: Markdown
   - Location: `/CODE_OF_CONDUCT.md`
   - Content: Contributor Covenant v2.1
   - Status: ❌ Missing

4. **CONTRIBUTING.md**
   - Type: Markdown
   - Location: `/CONTRIBUTING.md`
   - Content: Development setup, PR guidelines, code standards
   - Status: ❌ Missing

5. **.github/ISSUE_TEMPLATE/bug_report.md**
   - Type: Markdown (GitHub template)
   - Location: `.github/ISSUE_TEMPLATE/bug_report.md`
   - Content: Bug report template with fields
   - Status: ❌ Missing (directory doesn't exist)

6. **.github/ISSUE_TEMPLATE/feature_request.md**
   - Type: Markdown (GitHub template)
   - Location: `.github/ISSUE_TEMPLATE/feature_request.md`
   - Content: Feature request template
   - Status: ❌ Missing

7. **.github/PULL_REQUEST_TEMPLATE.md**
   - Type: Markdown (GitHub template)
   - Location: `.github/PULL_REQUEST_TEMPLATE.md`
   - Content: PR template with checklist
   - Status: ❌ Missing

8. **.github/workflows/ci.yml**
   - Type: YAML (GitHub Actions)
   - Location: `.github/workflows/ci.yml`
   - Content: Lint, type check, test workflow
   - Status: ❌ Missing

### High Priority - Should create before launch

9. **MAINTAINERS.md**
   - Type: Markdown
   - Location: `/MAINTAINERS.md`
   - Content: Core team, roles, governance
   - Status: ❌ Missing

10. **.github/dependabot.yml**
    - Type: YAML
    - Location: `.github/dependabot.yml`
    - Content: Dependency update configuration
    - Status: ❌ Missing

11. **.editorconfig**
    - Type: EditorConfig format
    - Location: `/.editorconfig`
    - Content: Consistent editor settings
    - Status: ❌ Missing

12. **.pre-commit-config.yaml**
    - Type: YAML
    - Location: `.pre-commit-config.yaml`
    - Content: Pre-commit hook configuration
    - Status: ❌ Missing

13. **tests/conftest.py**
    - Type: Python
    - Location: `/tests/conftest.py`
    - Content: Pytest fixtures and configuration
    - Status: ❌ Missing (no tests directory)

14. **tests/unit/test_agent.py**
    - Type: Python
    - Location: `/tests/unit/test_agent.py`
    - Content: Unit tests for core agent
    - Status: ❌ Missing

15. **.github/workflows/release.yml**
    - Type: YAML (GitHub Actions)
    - Location: `.github/workflows/release.yml`
    - Content: Automated release workflow
    - Status: ❌ Missing

### Recommended - Nice to have

16. **py.typed**
    - Type: Marker file
    - Location: `/src/benedict/py.typed`
    - Content: Empty file (marks package as typed)
    - Status: ❌ Missing

17. **.github/ISSUE_TEMPLATE/config.yml**
    - Type: YAML
    - Location: `.github/ISSUE_TEMPLATE/config.yml`
    - Content: Issue template configuration
    - Status: ❌ Missing

18. **.devcontainer/devcontainer.json**
    - Type: JSON
    - Location: `.devcontainer/devcontainer.json`
    - Content: VS Code devcontainer configuration
    - Status: ❌ Missing

19. **docs/FAQ.md**
    - Type: Markdown
    - Location: `/docs/FAQ.md`
    - Content: Frequently asked questions
    - Status: ❌ Missing

20. **.github/workflows/docs.yml**
    - Type: YAML (GitHub Actions)
    - Location: `.github/workflows/docs.yml`
    - Content: Documentation build/deploy
    - Status: ❌ Missing

---

## 📝 Files to MODIFY

### Critical modifications

1. **README.md**
   - Location: `/README.md`
   - Status: ✅ Exists (excellent quality)
   - Changes needed:
     - [ ] Line 186: Change `@michael` to `@alice`
     - [ ] Add badges (license, Python, CI) at top
     - [ ] Update clone URL from `<your-repo-url>` to actual public URL
     - [ ] Add contributing section linking to CONTRIBUTING.md
     - [ ] Add code of conduct reference
     - [ ] Add security policy reference
     - [ ] Add "⭐ Star us on GitHub" call-to-action
     - [ ] Update "Support" section with proper contact info

2. **src/benedict/workspace/workspace_manager.py**
   - Location: `/src/benedict/workspace/workspace_manager.py`
   - Status: ✅ Exists
   - Changes needed:
     - [ ] Line 102: Change comment `mkarots/hookedllm` to `example-org/example-repo`

3. **src/benedict/agent.py**
   - Location: `/src/benedict/agent.py`
   - Status: ✅ Exists
   - Changes needed:
     - [ ] Line 219: Change comment `mkarots/hookedllm` to `example-org/example-repo`

4. **src/benedict/commands/command_definitions.py**
   - Location: `/src/benedict/commands/command_definitions.py`
   - Status: ✅ Exists
   - Changes needed:
     - [ ] Line 76: Change `mkarots/benedict` to `example-org/example-repo`

5. **plans/slack-agent-architecture.md**
   - Location: `/plans/slack-agent-architecture.md`
   - Status: ✅ Exists
   - Changes needed:
     - [ ] Line 148: Change `@michael` to `@alice`

6. **plans/implementation-plan.md**
   - Location: `/plans/implementation-plan.md`
   - Status: ✅ Exists
   - Changes needed:
     - [ ] Line 131: Change `@michael` to `@alice`

### High priority modifications

7. **pyproject.toml**
   - Location: `/pyproject.toml`
   - Status: ✅ Exists (good structure)
   - Changes needed:
     - [ ] Add `license` field: `license = {text = "MIT"}`
     - [ ] Add `authors` field with maintainer info
     - [ ] Add `repository` URL field
     - [ ] Add `homepage` URL field
     - [ ] Add `keywords` field for PyPI
     - [ ] Add `classifiers` for PyPI
     - [ ] Consider version bump to 1.0.0 or 0.4.0
     - [ ] Add `pytest` and `pytest-cov` to dev dependencies
     - [ ] Add `mypy` to dev dependencies

8. **.gitignore**
   - Location: `/.gitignore`
   - Status: ✅ Exists (good coverage)
   - Changes needed:
     - [ ] Add `.pytest_cache/`
     - [ ] Add `.mypy_cache/`
     - [ ] Add `.ruff_cache/`
     - [ ] Add `htmlcov/`
     - [ ] Add `.coverage`
     - [ ] Add `.tox/`

9. **CHANGELOG.md**
   - Location: `/CHANGELOG.md`
   - Status: ✅ Exists (well maintained)
   - Changes needed:
     - [ ] Add section for next release (1.0.0 or 0.4.0)
     - [ ] Document "Open Source Launch" milestone
     - [ ] Ensure format follows Keep a Changelog
     - [ ] Add links to compare versions

10. **Makefile**
    - Location: `/Makefile`
    - Status: ✅ Exists
    - Changes needed:
      - [ ] Add `test` target for running pytest
      - [ ] Add `test-cov` target for coverage report
      - [ ] Add `type-check` target for mypy
      - [ ] Add `pre-commit` target for running hooks
      - [ ] Update `lint` target to include mypy
      - [ ] Add `build` target for package building
      - [ ] Add `publish-test` target for TestPyPI
      - [ ] Add `publish` target for PyPI

### Recommended modifications

11. **docs/SLACK_SETUP.md**
    - Location: `/docs/SLACK_SETUP.md`
    - Status: ✅ Exists (excellent quality)
    - Changes needed:
      - [ ] Review for any personal references
      - [ ] Add link to troubleshooting in main README

12. **plans/ARCHITECTURE.md**
    - Location: `/plans/ARCHITECTURE.md`
    - Status: ✅ Exists (excellent quality)
    - Changes needed:
      - [ ] Add testing architecture section
      - [ ] Document CI/CD integration points
      - [ ] Add contribution workflow diagram

---

## 🔍 Files to REVIEW (No changes expected)

These files should be reviewed but likely don't need changes:

1. **All Python source files** (`src/benedict/**/*.py`)
   - Review for: Hardcoded credentials, personal info, TODO comments
   - Action: Code review pass

2. **Documentation files** (`docs/*.md`)
   - Review for: Personal references, outdated information
   - Current files:
     - `docs/COMMAND_CLASSIFIER_DESIGN.md` ✅
     - `docs/CODE_READING_GUIDE.md` ✅
     - `docs/SLACK_SETUP.md` ✅ (minor changes needed)
     - `docs/COMMAND_CLASSIFIER_API_DESIGN.md` ✅
     - `docs/LLM_COMMAND_CLASSIFIER_DESIGN.md` ✅

3. **Planning documents** (`plans/*.md`)
   - Review for: Personal references, outdated roadmaps
   - Current files:
     - `plans/MILESTONE_STATUS.md` ✅
     - `plans/M2_Channel_History_Indexing.md` ✅
     - `plans/slack-agent-architecture.md` ⚠️ (changes needed)
     - `plans/M1_LLM_Integration.md` ✅
     - `plans/implementation-plan.md` ⚠️ (changes needed)
     - `plans/ARCHITECTURE.md` ⚠️ (changes needed)

4. **CLAUDE.MD**
   - Location: `/CLAUDE.MD`
   - Status: ✅ Good (internal development guidelines)
   - Action: Review if this should be public or moved to internal docs

5. **.benedict.method.yaml**
   - Location: `/.benedict.method.yaml`
   - Status: ✅ Exists
   - Action: Review content for sensitive information

---

## 🗂️ Directory Structure Changes

### Directories to CREATE

```
.github/
├── ISSUE_TEMPLATE/
│   ├── bug_report.md
│   ├── feature_request.md
│   └── config.yml
├── workflows/
│   ├── ci.yml
│   ├── release.yml
│   └── docs.yml (optional)
└── PULL_REQUEST_TEMPLATE.md

tests/
├── unit/
│   ├── __init__.py
│   ├── test_agent.py
│   ├── test_commands/
│   ├── test_workspace/
│   ├── test_metadata/
│   └── test_utils/
├── integration/
│   ├── __init__.py
│   ├── test_slack_integration.py
│   ├── test_llm_integration.py
│   └── test_semantic_search.py
├── fixtures/
│   └── __init__.py
└── conftest.py

.devcontainer/ (optional)
└── devcontainer.json
```

### Directories to REVIEW

- `src/benedict/` - Main source (thorough code review)
- `docs/` - Documentation (review for completeness)
- `plans/` - Planning docs (review for relevance)

---

## 📊 File Creation Priority Matrix

### Phase 1: Critical (Complete before public)
```
1. LICENSE                                    [NEW] 🔴
2. SECURITY.md                               [NEW] 🔴
3. CODE_OF_CONDUCT.md                        [NEW] 🔴
4. CONTRIBUTING.md                           [NEW] 🔴
5. .github/ISSUE_TEMPLATE/*.md               [NEW] 🔴
6. .github/PULL_REQUEST_TEMPLATE.md          [NEW] 🔴
7. README.md                                 [MODIFY] 🔴
8. Remove personal info (6 files)            [MODIFY] 🔴
```

### Phase 2: High Priority (Before heavy promotion)
```
9. .github/workflows/ci.yml                  [NEW] 🟡
10. tests/conftest.py + basic tests          [NEW] 🟡
11. .pre-commit-config.yaml                  [NEW] 🟡
12. .editorconfig                            [NEW] 🟡
13. .github/dependabot.yml                   [NEW] 🟡
14. pyproject.toml enhancements              [MODIFY] 🟡
15. .gitignore updates                       [MODIFY] 🟡
16. Makefile enhancements                    [MODIFY] 🟡
```

### Phase 3: Recommended (Nice to have)
```
17. .github/workflows/release.yml            [NEW] 🟢
18. Comprehensive test suite                 [NEW] 🟢
19. MAINTAINERS.md                          [NEW] 🟢
20. py.typed                                [NEW] 🟢
21. .devcontainer/                          [NEW] 🟢
22. docs/FAQ.md                             [NEW] 🟢
```

---

## 🛠️ Implementation Order

### Week 1: Legal & Safety
1. Create LICENSE
2. Scan git history for secrets
3. Create SECURITY.md
4. Create CODE_OF_CONDUCT.md
5. Remove personal information from code

### Week 2: Community Infrastructure
6. Create CONTRIBUTING.md
7. Create GitHub issue templates
8. Create PR template
9. Update README with badges and links
10. Create MAINTAINERS.md

### Week 3: Code Quality
11. Set up .pre-commit-config.yaml
12. Set up .editorconfig
13. Create basic test structure
14. Add type hints to critical modules
15. Update .gitignore

### Week 4: Automation
16. Create CI workflow
17. Set up Dependabot
18. Update Makefile with new targets
19. Update pyproject.toml
20. Create release workflow

### Week 5+: Testing & Polish
21. Write comprehensive tests
22. Achieve target code coverage
23. Create FAQ
24. Final documentation review
25. Prepare launch materials

---

## 📋 Quick Reference: What Exists vs What's Needed

| Category | Exists | Missing | Needs Update |
|----------|--------|---------|--------------|
| License | ❌ | LICENSE | - |
| Security | ❌ | SECURITY.md | - |
| Community | ❌ | CODE_OF_CONDUCT, CONTRIBUTING | README |
| CI/CD | ❌ | All workflows | - |
| Tests | ❌ | Entire test suite | - |
| GitHub | ❌ | Issue/PR templates | - |
| Config | ✅ .gitignore | .editorconfig, .pre-commit | .gitignore, pyproject.toml |
| Docs | ✅ Excellent | FAQ, MAINTAINERS | Minor updates to 6 files |

**Summary**: 
- 20 new files to create
- 12 existing files to modify
- 5+ directories to create

---

## ✅ Validation Checklist

Before considering the repository "launch ready":

```
Documentation:
[ ] LICENSE file exists with correct copyright
[ ] SECURITY.md explains vulnerability reporting
[ ] CODE_OF_CONDUCT.md is present
[ ] CONTRIBUTING.md has clear guidelines
[ ] README has all badges and links updated
[ ] All personal references removed

GitHub Setup:
[ ] Issue templates working
[ ] PR template working
[ ] CI workflow running successfully
[ ] Dependabot configured
[ ] Branch protection enabled
[ ] Repository settings configured (topics, description)

Code Quality:
[ ] Basic tests passing
[ ] Pre-commit hooks set up
[ ] Type checking passes
[ ] Linters pass
[ ] No secrets in git history

Package:
[ ] pyproject.toml complete
[ ] Package builds successfully
[ ] Can install from built package
[ ] Entry point works
```

---

**Last Updated**: 2026-08-14
**Status**: Planning Complete - Ready for Implementation
