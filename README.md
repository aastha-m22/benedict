# Slack Repo Agent - v0

A minimal Slack bot that links channels to repositories, providing a foundation for repo-scoped AI agent conversations.

## Overview

This is **v0** - a proof-of-concept skeleton that demonstrates:
- ✅ Slack bot responding to @mentions
- ✅ Channel → Repository mapping
- ✅ Persistent state across restarts
- ✅ Thread-based conversations
- ❌ LLM integration (coming in v1)
- ❌ GitHub API integration (coming in v1)
- ❌ Notion/GDocs access (coming in v2)

## Features

### Commands

1. **Onboard a channel**
   ```
   @agent onboard repo foo/bar
   ```
   Links the current channel to a repository.

2. **Check status**
   ```
   @agent status
   ```
   Shows which repository the channel is linked to.

3. **Ask questions** (stub response in v0)
   ```
   @agent what's the architecture?
   ```
   The bot acknowledges but doesn't provide intelligent answers yet.

## Prerequisites

- Python 3.8 or higher
- A Slack workspace where you can create apps
- Admin access to install apps to the workspace

## Slack App Setup

### Step 1: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter app name: `Repo Agent` (or your preferred name)
5. Select your workspace
6. Click **"Create App"**

### Step 2: Enable Socket Mode

1. In your app settings, go to **"Socket Mode"** (under Settings in the sidebar)
2. Toggle **"Enable Socket Mode"** to ON
3. You'll be prompted to create an app-level token:
   - Token Name: `socket-token` (or any name)
   - Scope: `connections:write`
   - Click **"Generate"**
4. **Copy the token** (starts with `xapp-`) - you'll need this for `SLACK_APP_TOKEN`

### Step 3: Add Bot Token Scopes

1. Go to **"OAuth & Permissions"** (under Features in the sidebar)
2. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
3. Click **"Add an OAuth Scope"** and add these scopes:
   - `chat:write` - Send messages
   - `channels:history` - Read channel messages
   - `channels:read` - View channel info

### Step 4: Subscribe to Events

1. Go to **"Event Subscriptions"** (under Features in the sidebar)
2. Toggle **"Enable Events"** to ON
3. Under **"Subscribe to bot events"**, click **"Add Bot User Event"**
4. Add this event:
   - `app_mention` - When the bot is @mentioned

### Step 5: Install App to Workspace

1. Go to **"Install App"** (under Settings in the sidebar)
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. **Copy the "Bot User OAuth Token"** (starts with `xoxb-`) - you'll need this for `SLACK_BOT_TOKEN`

### Step 6: Note Your Tokens

You should now have two tokens:
- **Bot Token** (`xoxb-...`) - from OAuth & Permissions
- **App Token** (`xapp-...`) - from Socket Mode

## Installation

### 1. Clone or Download

```bash
git clone <your-repo-url>
cd slack-repo-agent
```

Or download the files directly.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or using a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project directory:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
```

Replace the values with your actual tokens from the Slack App setup.

### 4. Run the Bot

```bash
python app.py
```

You should see:
```
✅ Bot is running! Press Ctrl+C to stop.
```

## Usage

### 1. Invite the Bot to a Channel

In any Slack channel, type:
```
/invite @Repo Agent
```
(Use whatever name you gave your bot)

### 2. Onboard the Channel

Tell the bot which repository this channel is about:
```
@Repo Agent onboard repo foo/bar
```

The bot will confirm:
```
✅ Onboarded! This channel is now linked to `foo/bar`.
I'll remember this repo for all our conversations here.
```

### 3. Check Status

```
@Repo Agent status
```

Response:
```
📊 Channel Status
━━━━━━━━━━━━━━━
📺 Channel: #proj-foo
🔗 Repository: foo/bar
⏰ Onboarded: 2026-02-01 20:30 UTC
👤 By: @michael
```

### 4. Ask Questions (v0 stub)

```
@Repo Agent what files handle authentication?
```

Response:
```
I'm your agent for `foo/bar`. 🤖

(LLM integration not connected yet, but I know we're talking about foo/bar!)

You asked: what files handle authentication?
```

## Testing Checklist

Use this checklist to verify everything works:

### Basic Setup
- [ ] Created Slack app
- [ ] Enabled Socket Mode
- [ ] Added bot scopes (`chat:write`, `channels:history`, `channels:read`)
- [ ] Subscribed to `app_mention` event
- [ ] Installed app to workspace
- [ ] Copied both tokens (bot token and app token)
- [ ] Created `.env` file with tokens
- [ ] Installed Python dependencies
- [ ] Started bot successfully

### Single Channel Test
- [ ] Created test channel `#test-foo`
- [ ] Invited bot to channel
- [ ] Tried talking without onboarding (should get prompt)
- [ ] Onboarded: `@agent onboard repo foo/bar`
- [ ] Got success confirmation
- [ ] Checked status: `@agent status`
- [ ] Asked question: `@agent what's the code structure?`
- [ ] Got stub response mentioning the repo

### Multiple Channels Test
- [ ] Created second channel `#test-bar`
- [ ] Invited bot to second channel
- [ ] Onboarded: `@agent onboard repo baz/qux`
- [ ] Verified status shows different repo
- [ ] Went back to first channel
- [ ] Verified status still shows `foo/bar`

### Persistence Test
- [ ] Stopped bot (Ctrl+C)
- [ ] Verified `state.json` file exists
- [ ] Checked `state.json` contains channel mappings
- [ ] Restarted bot
- [ ] Checked status in channel (should still show repo)

### Edge Cases
- [ ] Onboarded same channel twice (should update)
- [ ] Tried invalid repo format (should show error)
- [ ] Tried status in non-onboarded channel (should prompt)

## File Structure

```
slack-repo-agent/
├── app.py              # Main bot application (~250 lines)
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── .env               # Your tokens (DO NOT COMMIT)
├── .env.example       # Template for .env
├── .gitignore         # Git ignore rules
└── state.json         # Runtime state (created automatically)
```

## State File

The bot stores channel mappings in `state.json`:

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

This file is created automatically and persists across restarts.

## Troubleshooting

### Bot doesn't respond

**Check:**
1. Is the bot running? (`python app.py` should show "Bot is running!")
2. Is the bot invited to the channel? (`/invite @Repo Agent`)
3. Are you @mentioning the bot? (Just typing won't work)
4. Check the terminal for error messages

### "Missing SLACK_BOT_TOKEN" error

**Fix:**
1. Make sure `.env` file exists in the same directory as `app.py`
2. Verify the file contains `SLACK_BOT_TOKEN=xoxb-...`
3. Make sure there are no spaces around the `=`
4. Restart the bot after creating/editing `.env`

### "Missing SLACK_APP_TOKEN" error

**Fix:**
1. Make sure Socket Mode is enabled in your Slack app settings
2. Create an app-level token with `connections:write` scope
3. Add `SLACK_APP_TOKEN=xapp-...` to your `.env` file
4. Restart the bot

### Bot responds but says "This channel hasn't been onboarded yet"

**Fix:**
1. Run the onboard command: `@agent onboard repo your-org/your-repo`
2. Make sure you're using the format `org/repo` (e.g., `acme/widget`)

### State file gets corrupted

**Fix:**
1. Stop the bot
2. Delete `state.json`
3. Restart the bot (it will create a new empty state)
4. Re-onboard your channels

### Bot responds in channel instead of thread

This is expected behavior in v0. The bot replies in-thread to keep conversations organized.

## Development

### Running in Development

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run with debug logging
python app.py
```

### Project Structure

- **State Management** (`load_state`, `save_state`, `get_channel_repo`, `set_channel_repo`)
  - Handles JSON persistence
  - Thread-safe for single-process use

- **Command Detection** (`is_onboard_command`, `is_status_command`, `extract_repo_name`)
  - Simple pattern matching
  - Flexible parsing for natural language

- **Event Handlers** (`handle_app_mention`, `handle_onboard`, `handle_status`, `handle_conversation`)
  - Routes @mentions to appropriate handlers
  - Always replies in thread

## Roadmap

### v0 (Current) ✅
- Slack connection via Socket Mode
- Channel → Repo mapping
- Onboard & status commands
- Stub conversation responses

### v1 (Next)
- LLM integration (Claude/GPT-4)
- GitHub API: read repo files
- Basic code Q&A
- Intelligent responses

### v2 (Future)
- Notion integration
- Google Docs access
- Cursor session logs
- Multi-repo context

### v3 (Advanced)
- Agent-to-agent communication
- RAG/vector search over codebase
- Proactive suggestions
- Code review automation

## Contributing

This is a proof-of-concept. Contributions welcome!

## License

MIT License - feel free to use and modify.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review Slack app configuration
3. Check terminal logs for error messages
4. Verify `.env` file is correctly formatted

## Architecture

See [`plans/slack-agent-architecture.md`](plans/slack-agent-architecture.md) for detailed architecture documentation.

