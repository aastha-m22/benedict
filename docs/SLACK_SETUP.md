# Slack App Setup Guide

Complete step-by-step guide for setting up your Slack app for the Repo Agent bot.

## Prerequisites

- A Slack workspace where you can create apps
- Admin access to install apps to the workspace

## Step 1: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter app name: `Repo Agent` (or your preferred name)
5. Select your workspace
6. Click **"Create App"**

## Step 2: Enable Socket Mode

Socket Mode allows the bot to connect to Slack without exposing a public webhook URL.

1. In your app settings, go to **"Socket Mode"** (under Settings in the sidebar)
2. Toggle **"Enable Socket Mode"** to ON
3. You'll be prompted to create an app-level token:
   - Token Name: `socket-token` (or any name)
   - Scope: `connections:write`
   - Click **"Generate"**
4. **Copy the token** (starts with `xapp-`) - you'll need this for `SLACK_APP_TOKEN`

⚠️ **Important**: Save this token securely. You'll add it to your `.env` file.

## Step 3: Add Bot Token Scopes

These scopes define what the bot can do in your workspace.

1. Go to **"OAuth & Permissions"** (under Features in the sidebar)
2. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
3. Click **"Add an OAuth Scope"** and add these scopes:
   - `chat:write` - Send messages
   - `channels:history` - Read channel messages
   - `channels:read` - View channel info

## Step 4: Subscribe to Events

The bot needs to listen for when it's mentioned.

1. Go to **"Event Subscriptions"** (under Features in the sidebar)
2. Toggle **"Enable Events"** to ON
3. Under **"Subscribe to bot events"**, click **"Add Bot User Event"**
4. Add this event:
   - `app_mention` - When the bot is @mentioned

## Step 5: Install App to Workspace

Install the app to your workspace so it can access channels.

1. Go to **"Install App"** (under Settings in the sidebar)
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. **Copy the "Bot User OAuth Token"** (starts with `xoxb-`) - you'll need this for `SLACK_BOT_TOKEN`

⚠️ **Important**: Save this token securely. You'll add it to your `.env` file.

## Step 6: Note Your Tokens

You should now have two tokens:

- **Bot Token** (`xoxb-...`) - from OAuth & Permissions
  - Used for API calls (sending messages, reading history)
- **App Token** (`xapp-...`) - from Socket Mode
  - Used for Socket Mode connection

## Step 7: Configure Environment Variables

Add both tokens to your `.env` file:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
```

Replace the values with your actual tokens from Steps 2 and 5.

## Step 8: Invite Bot to Channels

After starting the bot, invite it to channels where you want to use it:

```
/invite @Repo Agent
```

(Use whatever name you gave your bot)

## Verification Checklist

Use this checklist to verify your setup:

- [ ] Created Slack app at api.slack.com/apps
- [ ] Enabled Socket Mode
- [ ] Created app-level token with `connections:write` scope
- [ ] Copied app token (`xapp-...`)
- [ ] Added bot scopes (`chat:write`, `channels:history`, `channels:read`)
- [ ] Subscribed to `app_mention` event
- [ ] Installed app to workspace
- [ ] Copied bot token (`xoxb-...`)
- [ ] Added both tokens to `.env` file
- [ ] Started bot successfully (`make run` or `python main.py`)
- [ ] Invited bot to a test channel
- [ ] Tested @mention in channel

## Troubleshooting

### "Missing SLACK_BOT_TOKEN" error

**Fix:**
1. Make sure `.env` file exists in the project directory
2. Verify the file contains `SLACK_BOT_TOKEN=xoxb-...`
3. Make sure there are no spaces around the `=`
4. Restart the bot after creating/editing `.env`

### "Missing SLACK_APP_TOKEN" error

**Fix:**
1. Make sure Socket Mode is enabled in your Slack app settings
2. Create an app-level token with `connections:write` scope
3. Add `SLACK_APP_TOKEN=xapp-...` to your `.env` file
4. Restart the bot

### Bot doesn't respond to @mentions

**Check:**
1. Is the bot running? (`python main.py` should show "Bot is running!")
2. Is the bot invited to the channel? (`/invite @Repo Agent`)
3. Are you @mentioning the bot? (Just typing won't work)
4. Check the terminal for error messages
5. Verify `app_mention` event is subscribed in Event Subscriptions

### Bot can't read channel history

**Fix:**
1. Verify `channels:history` scope is added in OAuth & Permissions
2. Reinstall the app to workspace after adding scopes
3. Make sure bot is invited to the channel

## Security Notes

- **Never commit tokens to git** - Keep `.env` in `.gitignore`
- **Rotate tokens if exposed** - If a token is leaked, regenerate it immediately
- **Use workspace-specific tokens** - Don't share tokens across workspaces
- **Limit bot access** - Only invite bot to channels where it's needed

## Next Steps

After completing setup:

1. See [README.md](README.md) for usage instructions
2. Onboard a channel: `@agent onboard repo your-org/your-repo`
3. Check status: `@agent status`
4. Start asking questions about your repository!
