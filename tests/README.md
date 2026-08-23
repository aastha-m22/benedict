# Benedict Test Suite

Comprehensive test suite for the Benedict Slack repository agent.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── unit/                    # Unit tests for individual components
│   ├── test_models.py       # Message, Conversation, ConversationManager
│   ├── test_agent.py        # RepoAgent core logic
│   ├── test_workspace.py    # WorkspaceManager, ActionLogger
│   ├── test_utils.py        # Utility functions (context building, etc.)
│   ├── test_llm.py          # LLM implementations (Mock)
│   ├── test_repo_reader.py  # Repository reader implementations
│   └── test_conversation_repository.py  # Persistence implementations
└── integration/             # Integration tests for multiple components
    ├── test_agent_integration.py  # Agent with dependencies
    └── test_end_to_end.py        # Complete workflows
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=src/benedict --cov-report=html
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_models.py

# Specific test class
pytest tests/unit/test_models.py::TestMessage

# Specific test function
pytest tests/unit/test_models.py::TestMessage::test_create_message
```

### Run with Markers
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Verbose Output
```bash
pytest -v

# Even more verbose
pytest -vv
```

### Stop on First Failure
```bash
pytest -x
```

### Run Failed Tests from Last Run
```bash
pytest --lf
```

## Writing Tests

### Test Structure

Tests follow the Arrange-Act-Assert (AAA) pattern:

```python
def test_example(self, fixture):
    # Arrange - Set up test data and dependencies
    agent = RepoAgent(state_file="test.json")
    
    # Act - Execute the code being tested
    result = agent.do_something()
    
    # Assert - Verify the expected outcome
    assert result == expected_value
```

### Using Fixtures

Fixtures are defined in `conftest.py` and can be used in any test:

```python
def test_with_fixtures(self, mock_llm, mock_repo_reader):
    """Test using shared fixtures."""
    agent = RepoAgent(llm=mock_llm, repo_reader=mock_repo_reader)
    # Test logic here
```

### Common Fixtures

- `temp_dir`: Temporary directory for file operations
- `temp_state_file`: Temporary state file path
- `mock_llm`: Mock LLM implementation
- `mock_repo_reader`: Mock repository reader with sample files
- `mock_semantic_indexer`: Mock semantic search
- `mock_conversation_repository`: Mock conversation persistence
- `sample_conversation`: Pre-populated conversation
- `sample_message`: Sample message object

### Test Naming

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

Use descriptive names that explain what is being tested:
```python
def test_add_message_updates_timestamp(self):
    """Test that adding message updates the updated_at timestamp."""
    # ...
```

## Test Coverage

### View Coverage Report

After running tests with coverage:
```bash
# Terminal report
pytest --cov=src/benedict --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=src/benedict --cov-report=html
open htmlcov/index.html
```

### Coverage Goals

- **Overall**: >80% code coverage
- **Core components**: >90% coverage
  - `models/conversation.py`
  - `agent.py` (command parsing, state management)
  - Repository implementations
- **Integration**: All critical workflows covered

### Coverage Exclusions

Lines excluded from coverage (configured in `pytest.ini`):
- `pragma: no cover`
- Abstract methods
- `if __name__ == '__main__':`
- Type checking blocks
- Debug/repr methods

## Test Categories (Markers)

Tests can be marked with categories:

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_workflow():
    pass

@pytest.mark.slow
def test_long_running():
    pass
```

Run specific categories:
```bash
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

## Mock Objects

### Mock LLM

```python
from benedict.llm import MockLLM

llm = MockLLM()
llm.set_response("Custom response")
response = llm.generate(system_prompt="...", user_message="...")
```

### Mock Repository Reader

```python
from benedict.repo_reader import MockRepoReader

reader = MockRepoReader()
reader.add_file("README.md", "# Content")
content = reader.read_file("README.md")
```

### Mock Semantic Indexer

```python
from benedict.semantic_indexer import MockSemanticIndexer

indexer = MockSemanticIndexer()
indexer.add_relevant_file("file.py", relevance_score=0.9)
results = indexer.search("query", top_k=5)
```

## Best Practices

### 1. Test Independence

Each test should be independent and not rely on other tests:
```python
# Good - Self-contained test
def test_create_message(self):
    message = Message(role="user", content="Hello")
    assert message.content == "Hello"

# Bad - Depends on class state from other tests
class TestBad:
    def test_step_1(self):
        self.data = "value"
    
    def test_step_2(self):
        assert self.data == "value"  # Fails if step_1 doesn't run first
```

### 2. Use Descriptive Assertions

```python
# Good
assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"

# Better
assert len(messages) == 2
assert messages[0].role == "user"
assert messages[1].role == "assistant"
```

### 3. Test Edge Cases

```python
def test_empty_input(self):
    result = function("")
    assert result is expected

def test_none_input(self):
    result = function(None)
    assert result is expected

def test_large_input(self):
    result = function("x" * 10000)
    assert result is expected
```

### 4. Test Error Handling

```python
def test_invalid_input_raises_error(self):
    with pytest.raises(ValueError, match="Invalid input"):
        function(invalid_input)
```

### 5. Use Parametrize for Multiple Cases

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_uppercase(input, expected):
    assert uppercase(input) == expected
```

## Continuous Integration

Tests run automatically in CI/CD:

```yaml
# .github/workflows/ci.yml
- name: Run tests
  run: pytest --cov=src/benedict --cov-report=xml
```

## Troubleshooting

### Import Errors

If you see import errors:
```bash
# Make sure pytest can find the source
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
pytest
```

Or use the configuration in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
```

### Fixture Not Found

Ensure `conftest.py` is in the correct location and fixtures are properly defined.

### Tests Pass Locally But Fail in CI

- Check for dependencies on local environment
- Ensure test data is not relying on absolute paths
- Verify all test dependencies are in `pyproject.toml`

## Contributing

When adding new features:

1. **Write tests first** (TDD approach preferred)
2. **Maintain >80% coverage** for new code
3. **Add fixtures to `conftest.py`** if they're reusable
4. **Document complex test scenarios** with docstrings
5. **Run full test suite** before submitting PR

### Pre-commit Checks

```bash
# Run tests
pytest

# Check coverage
pytest --cov=src/benedict --cov-report=term-missing

# Lint
ruff check tests/
black --check tests/
mypy tests/
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Testing Best Practices](https://docs.pytest.org/en/latest/goodpractices.html)

## Questions?

For questions about testing:
1. Check this README
2. Review existing tests for examples
3. See `conftest.py` for available fixtures
4. Consult the main project documentation
