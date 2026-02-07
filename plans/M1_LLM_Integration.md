# M1: LLM Integration

Agent gains intelligence through Claude integration with local repository access.

## 1. Overview

**What:**
Add Claude LLM to agent for intelligent responses. Use local filesystem to read repository code.

**Why:**
Current agent returns stub responses. Need actual intelligence to answer code questions.

**When to use:**
When user asks questions about repository code, architecture, or implementation.

## 2. Non-Goals

- No GitHub API integration (M2)
- No memory system (M6)
- No skills system (M5)
- No event handling (M8)

Just: LLM + local repo reading + composition pattern.

## 3. Key Concepts

| Term | Meaning |
|------|---------|
| LLM | Large Language Model (Claude 3.5 Sonnet) |
| Protocol | Python interface definition (no implementation) |
| Repo Reader | Tool that reads repository files from local filesystem |
| Context | Relevant code snippets sent to LLM with question |
| Composition Root | main.py where all concrete classes are instantiated |

## 4. High-Level Design

### Components

```
main.py (composition root)
  ├─> llm = ClaudeLLM(api_key)
  ├─> repo_reader = LocalRepoReader(base_path)
  └─> agent = RepoAgent(llm, repo_reader)
```

### Data Flow

1. User asks question in Slack
2. Agent gets repo name from channel mapping
3. Repo reader loads relevant files from local filesystem
4. Agent builds context (README + relevant files)
5. Agent sends context + question to Claude
6. Claude generates response
7. Agent returns response to Slack

### Key Invariants

- LLM is injected, never instantiated in agent
- Repo reader is injected, never instantiated in agent
- All file I/O happens in repo reader, not agent
- Agent doesn't know about Claude or filesystem

## 5. API / Interface

### LLM Protocol

```python
class LLM(Protocol):
    def generate(
        self, 
        prompt: str, 
        system: str = "",
        max_tokens: int = 2000
    ) -> str:
        """Generate response from prompt."""
```

### RepoReader Protocol

```python
class RepoReader(Protocol):
    def read_file(self, repo: str, path: str) -> str:
        """Read single file content."""
    
    def list_files(self, repo: str, path: str = "") -> List[str]:
        """List files in directory."""
    
    def file_exists(self, repo: str, path: str) -> bool:
        """Check if file exists."""
```

### Agent Update

```python
class RepoAgent:
    def __init__(
        self,
        state_file: str = "state.json",
        llm: Optional[LLM] = None,
        repo_reader: Optional[RepoReader] = None
    ):
        self.llm = llm
        self.repo_reader = repo_reader
```

## 6. Happy Path Example

**Step 1:** User onboards channel
```
@agent onboard repo my-project
```

**Step 2:** User asks question
```
@agent what's the authentication flow?
```

**Step 3:** Agent processes
- Gets repo: `my-project`
- Maps to local path: `/repos/my-project`
- Reads README.md
- Searches for auth-related files
- Reads `auth.py`, `middleware/auth.py`

**Step 4:** Agent builds context
```
Repository: my-project

README.md:
# My Project
Authentication uses JWT tokens...

auth.py:
def login(username, password):
    # Validate credentials
    ...

middleware/auth.py:
def auth_required(f):
    # Decorator for protected routes
    ...
```

**Step 5:** Agent calls Claude
```
System: You are a technical engineer assistant.

User: Repository: my-project
[context above]

Question: what's the authentication flow?
```

**Step 6:** Claude responds
```
Authentication Flow:

1. User logs in via login() in auth.py
2. Server validates credentials
3. JWT token issued
4. Client includes token in requests
5. auth_required decorator validates token

Key files:
- auth.py: Login logic
- middleware/auth.py: Token validation
```

**Step 7:** Agent posts to Slack
```
**Authentication Flow:**

1. User logs in via login() in auth.py
2. Server validates credentials
3. JWT token issued
4. Client includes token in requests
5. auth_required decorator validates token

**Key files:**
- auth.py: Login logic
- middleware/auth.py: Token validation
```

## 7. Edge Cases & Failure Modes

**Repo not found locally:**
- Check if path exists
- Return: "Repository not found at /repos/my-project"

**File read error:**
- Catch exception
- Return: "Could not read file: [path]"

**Claude API error:**
- Retry once with exponential backoff
- If fails: "LLM temporarily unavailable"

**Context too large:**
- Truncate to fit Claude's context window
- Prioritize: README > relevant files > structure

**No relevant files found:**
- Just use README
- Inform user: "Based on README only"

## 8. Constraints & Assumptions

**Performance:**
- Claude API: ~2-5s response time
- File I/O: <100ms for typical repos
- Total response time: <10s target

**Cost:**
- Claude 3.5 Sonnet: ~$3 per million input tokens
- Typical question: ~5K tokens input, 500 tokens output
- Cost per question: ~$0.02

**Security:**
- Local repos only (no remote access)
- Read-only filesystem access
- No code execution

**Limits:**
- Claude context window: 200K tokens
- Reserve 2K for response
- Use up to 198K for context

## 9. Alternatives Considered

**Option A: GitHub API instead of local**
- Rejected: M1 focuses on local, GitHub is M2
- Trade-off: Local is simpler, no rate limits

**Option B: GPT-4 instead of Claude**
- Rejected: Claude chosen for better code understanding
- Trade-off: GPT-4 has larger ecosystem

**Option C: Embed entire repo in context**
- Rejected: Too large, exceeds context window
- Trade-off: Smart selection vs. complete context

## 10. Open Questions

**Q1:** How to map repo name to local path?
**A1:** Configuration file: `config/repos.json`

**Q2:** How to find relevant files?
**A2:** Simple keyword matching in filenames for M1

**Q3:** How to handle large files?
**A3:** Truncate to first 1000 lines

**Q4:** Retry strategy for Claude API?
**A4:** Retry once after 1s delay

## 11. Implementation Plan

### Phase 1: LLM Protocol & Implementation

**Files:**
- `llm.py` - Protocol definition
- `llm_claude.py` - Claude implementation
- `llm_mock.py` - Mock for testing

# main.py
import os
from agent import RepoAgent
from llm import create_llm
from repo_reader import create_repo_reader
from slack_app import create_slack_app

def main():
    """Root composition - wire everything together."""
    
    # Create LLM
    llm = create_llm(provider="claude")
    
    # Create repo reader
    repo_reader = create_repo_reader(source="local")
    
    # Create agent with dependencies
    agent = RepoAgent(
        state_file="state.json",
        llm=llm,
        repo_reader=repo_reader
    )
    
    # Create and start Slack app
    slack_app = create_slack_app(agent)
    slack_app.start()

if __name__ == "__main__":
    main()
```

## 12. Testing Strategy

**Unit Tests:**
- Test LLM protocol with mock
- Test repo reader with test fixtures
- Test context builder with sample data
- Test agent with mocked dependencies

**Integration Tests:**
- Test with real Claude API (small test)
- Test with real local repository
- Test end-to-end flow

**Manual Tests:**
- Onboard test repository
- Ask various questions
- Verify responses are relevant
- Check response time

## 13. Success Criteria

- ✅ Agent responds with Claude-generated text
- ✅ Responses reference actual repository code
- ✅ Composition pattern working (dependencies injected)
- ✅ Response time < 10s
- ✅ Handles errors gracefully
- ✅ Tests passing

## 14. Dependencies

**New packages:**
```
anthropic>=0.18.0
```

**Environment variables:**
```
ANTHROPIC_API_KEY=sk-ant-...
```

**Directory structure:**
```
/repos/
  ├── my-project/
  │   ├── README.md
  │   ├── auth.py
  │   └── ...
  └── another-project/
      └── ...
```

## 15. Rollout Plan

1. **Implement** - Build all components
2. **Test locally** - Use test repository
3. **Deploy** - Update production bot
4. **Monitor** - Watch for errors
5. **Iterate** - Fix issues, improve context building

Ready to implement M1.
