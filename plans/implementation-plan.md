# Slack Repo Agent - Implementation Plan

## Summary
Building a minimal Slack bot that proves the concept of repo-scoped AI agents. This is v0 - infrastructure only, no LLM integration yet.

## What We're Building

### Core Features
1. **Slack Bot** that responds to @mentions
2. **Onboard Command** - Link a channel to a repository
3. **Status Command** - Show which repo a channel is linked to
4. **Conversation Stub** - Respond to questions (without LLM, just acknowledgment)
5. **State Persistence** - Remember channel→repo mappings across restarts

### What We're NOT Building (Yet)
- ❌ LLM integration (Claude/GPT-4)
- ❌ GitHub API integration
- ❌ Notion/Google Docs access
- ❌ Cursor session logs
- ❌ Agent-to-agent communication
- ❌ Complex command parsing

## Implementation Steps

### Step 1: Create [`app.py`](app.py)
**Purpose**: Main Slack bot application

**Components**:
1. **State Management** (~30 lines)
   - `load_state()` - Load from `state.json`
   - `save_state(state)` - Persist to `state.json`
   - `get_channel_repo(channel_id)` - Get repo for channel
   - `set_channel_repo(channel_id, repo, user_id)` - Store mapping

2. **Command Detection** (~20 lines)
   - `is_onboard_command(text)` - Check if text contains "onboard"
   - `is_status_command(text)` - Check if text contains "status"
   - `extract_repo_name(text)` - Parse repo from various formats

3. **Event Handler** (~40 lines)
   - `handle_app_mention(event, say)` - Main logic
     - Parse command type
     - Route to appropriate handler
     - Reply in thread

4. **Slack Setup** (~20 lines)
   - Initialize Bolt app
   - Register event handlers
   - Start Socket Mode

**Total**: ~150 lines

### Step 2: Create [`requirements.txt`](requirements.txt)
**Dependencies**:
```
slack-bolt>=1.18.0
python-dotenv>=1.0.0
```

### Step 3: Create [`README.md`](README.md)
**Sections**:
1. **Overview** - What this bot does
2. **Prerequisites** - Python 3.8+, Slack workspace
3. **Slack App Setup** - Step-by-step with screenshots
   - Create app
   - Enable Socket Mode
   - Add scopes
   - Subscribe to events
   - Get tokens
4. **Installation** - Clone, install deps, set env vars
5. **Usage** - How to onboard and use
6. **Testing Checklist** - Verify it works
7. **Troubleshooting** - Common issues

### Step 4: Create [`.env.example`](.env.example)
**Template**:
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
```

## File Structure
```
slack-repo-agent/
├── app.py              # Main application (~150 lines)
├── requirements.txt    # Dependencies (2 packages)
├── README.md          # Complete setup guide
├── .env.example       # Environment template
├── .env               # Your tokens (gitignored)
├── .gitignore         # Ignore .env and state.json
└── state.json         # Created at runtime
```

## State Schema

### [`state.json`](state.json)
```json
{
  "channels": {
    "C12345ABC": {
      "repo": "foo/bar",
      "onboarded_at": "2026-02-01T20:30:00Z",
      "onboarded_by": "U123456"
    }
  }
}
```

## Command Examples

### Onboard a Channel
```
@agent onboard repo foo/bar
```
Response:
```
✅ Onboarded! This channel is now linked to `foo/bar`.
I'll remember this repo for all our conversations here.
```

### Check Status
```
@agent status
```
Response:
```
📊 Channel Status
━━━━━━━━━━━━━━━
🔗 Repository: foo/bar
⏰ Onboarded: 2026-02-01 20:30 UTC
👤 By: @michael
```

### Ask a Question (Stub)
```
@agent what's the architecture?
```
Response:
```
I'm your agent for `foo/bar`. 
(LLM not connected yet, but I'm ready to learn about this repo!)
```

### Not Onboarded
```
@agent hello
```
Response:
```
⚠️ This channel hasn't been onboarded yet.
To get started: @agent onboard repo your-org/your-repo
```

## Testing Plan

### Manual Testing Checklist
1. **Setup**
   - [ ] Create Slack app
   - [ ] Configure Socket Mode
   - [ ] Add bot scopes
   - [ ] Install to workspace
   - [ ] Get tokens
   - [ ] Set environment variables

2. **Basic Functionality**
   - [ ] Start bot (`python app.py`)
   - [ ] Create test channel `#test-foo`
   - [ ] Invite bot to channel
   - [ ] Try talking without onboarding (should prompt)
   - [ ] Onboard: `@agent onboard repo foo/bar`
   - [ ] Check status: `@agent status`
   - [ ] Ask question: `@agent what files exist?`

3. **Multiple Channels**
   - [ ] Create `#test-bar`
   - [ ] Invite bot
   - [ ] Onboard: `@agent onboard repo baz/qux`
   - [ ] Verify different repos in each channel

4. **Persistence**
   - [ ] Stop bot (Ctrl+C)
   - [ ] Check `state.json` exists
   - [ ] Restart bot
   - [ ] Verify status still shows correct repo

5. **Edge Cases**
   - [ ] Onboard same channel twice (should update)
   - [ ] Invalid repo format
   - [ ] Empty message
   - [ ] Very long message

## Success Criteria

### Must Have
- ✅ Bot connects to Slack via Socket Mode
- ✅ Responds only to @mentions
- ✅ Replies in thread
- ✅ Onboard command works
- ✅ Status command works
- ✅ State persists to JSON
- ✅ Each channel has independent state
- ✅ README has complete setup instructions

### Nice to Have
- ✅ Natural language onboard parsing
- ✅ Helpful error messages
- ✅ Formatted status output
- ✅ Graceful error handling

## Next Steps (After v0)

Once this skeleton is working, we can add:

1. **LLM Integration** (v1)
   - Add OpenAI/Anthropic client
   - Pass questions to LLM with repo context
   - Return intelligent responses

2. **GitHub Integration** (v1)
   - Fetch repo files
   - Read code
   - Provide file-specific answers

3. **Advanced Context** (v2)
   - Notion pages
   - Google Docs
   - Cursor session logs

4. **Multi-Agent** (v3)
   - Agent-to-agent communication
   - Cross-repo coordination
   - Council channel

## Questions Before Implementation

1. **Slack Workspace**: Do you have admin access to create a Slack app?
2. **Python Version**: Do you have Python 3.8+ installed?
3. **Repository Format**: Should we support both `org/repo` and `github.com/org/repo`?
4. **Error Handling**: Should invalid repo formats be rejected or accepted anyway?
5. **Deployment**: Will this run locally or on a server?

## Ready to Build?

Once you approve this plan, I'll switch to **Code mode** and implement:
1. [`app.py`](app.py) - Complete Slack bot
2. [`requirements.txt`](requirements.txt) - Dependencies
3. [`README.md`](README.md) - Setup guide
4. [`.env.example`](.env.example) - Environment template
5. [`.gitignore`](.gitignore) - Ignore sensitive files

The implementation should take about 150 lines of clean, well-commented Python code.
