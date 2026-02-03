#!/usr/bin/env python3
"""
Slack Repo Agent - v0 Skeleton
A minimal Slack bot that links channels to repositories and provides a foundation
for repo-scoped AI agent conversations.
"""

import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
STATE_FILE = "state.json"
REPO_PATTERN = re.compile(r'([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)')

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


# ============================================================================
# State Management
# ============================================================================

def load_state() -> Dict[str, Any]:
    """Load state from JSON file. Create empty state if file doesn't exist."""
    state_path = Path(STATE_FILE)
    if state_path.exists():
        try:
            with open(state_path, 'r') as f:
                state = json.load(f)
                logger.info(f"Loaded state with {len(state.get('channels', {}))} channels")
                return state
        except json.JSONDecodeError:
            logger.error(f"Failed to parse {STATE_FILE}, creating new state")
    
    # Return empty state
    return {"channels": {}}


def save_state(state: Dict[str, Any]) -> None:
    """Persist state to JSON file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"Saved state with {len(state.get('channels', {}))} channels")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def get_channel_repo(channel_id: str) -> Optional[str]:
    """Get the repository associated with a channel."""
    state = load_state()
    channel_config = state.get("channels", {}).get(channel_id)
    if channel_config:
        return channel_config.get("repo")
    return None


def set_channel_repo(channel_id: str, repo: str, user_id: str) -> None:
    """Associate a repository with a channel."""
    state = load_state()
    if "channels" not in state:
        state["channels"] = {}
    
    state["channels"][channel_id] = {
        "repo": repo,
        "onboarded_at": datetime.utcnow().isoformat() + "Z",
        "onboarded_by": user_id
    }
    save_state(state)
    logger.info(f"Onboarded channel {channel_id} to repo {repo}")


# ============================================================================
# Command Detection & Parsing
# ============================================================================
def is_onboard_command(text: str) -> bool:
    """Check if the message is an onboard command."""
    text_lower = text.lower()
    return "onboard" in text_lower or "this channel is for" in text_lower


def is_status_command(text: str) -> bool:
    """Check if the message is a status command."""
    return "status" in text.lower()


def extract_repo_name(text: str) -> Optional[str]:
    """
    Extract repository name from text.
    Supports formats like:
    - foo/bar
    - github.com/foo/bar
    - repo foo/bar
    - repo: foo/bar
    """
    # Try to find org/repo pattern
    match = REPO_PATTERN.search(text)
    if match:
        return match.group(1)
    return None


# ============================================================================
# Event Handlers
# ============================================================================

@app.event("app_mention")
def handle_app_mention(event, say, client):
    """
    Handle @mentions of the bot.
    Routes to appropriate handler based on command type.
    """
    logger.info("=" * 60)
    logger.info("APP_MENTION EVENT RECEIVED!")
    logger.info(f"Full event: {json.dumps(event, indent=2)}")
    logger.info("=" * 60)
    
    try:
        channel_id = event["channel"]
        user_id = event["user"]
        text = event["text"]
        # Use thread_ts if message is in a thread, otherwise use ts to start a new thread
        thread_ts = event.get("thread_ts") or event.get("ts")
        
        # Remove bot mention from text for easier parsing
        # Bot mention format: <@U12345>
        text_clean = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
        
        logger.info(f"Processing mention in channel {channel_id}")
        logger.info(f"User: {user_id}")
        logger.info(f"Original text: {text}")
        logger.info(f"Cleaned text: {text_clean}")
        logger.info(f"Thread TS: {thread_ts}")
        
        # Route based on command type
        if is_onboard_command(text_clean):
            handle_onboard(channel_id, user_id, text_clean, say, thread_ts)
        elif is_status_command(text_clean):
            handle_status(channel_id, say, thread_ts, client)
        else:
            handle_conversation(channel_id, text_clean, say, thread_ts)
            
    except Exception as e:
        logger.error(f"Error handling app_mention: {e}", exc_info=True)
        say(
            text="⚠️ Sorry, I encountered an error processing your request.",
            thread_ts=thread_ts
        )


def handle_onboard(channel_id: str, user_id: str, text: str, say, thread_ts: str):
    """Handle onboard command."""
    repo = extract_repo_name(text)
    
    if not repo:
        say(
            text="⚠️ I couldn't find a repository name in your message.\n"
                 "Please use format: `@agent onboard repo foo/bar`",
            thread_ts=thread_ts
        )
        return
    
    # Save the mapping
    set_channel_repo(channel_id, repo, user_id)
    
    # Confirm success
    say(
        text=f"✅ Onboarded! This channel is now linked to `{repo}`.\n"
             f"I'll remember this repo for all our conversations here.\n\n"
             f"Try: `@agent status` to see the details.",
        thread_ts=thread_ts
    )


def handle_status(channel_id: str, say, thread_ts: str, client):
    """Handle status command."""
    state = load_state()
    channel_config = state.get("channels", {}).get(channel_id)
    
    if not channel_config:
        say(
            text="⚠️ This channel hasn't been onboarded yet.\n"
                 "To get started: `@agent onboard repo your-org/your-repo`",
            thread_ts=thread_ts
        )
        return
    
    repo = channel_config.get("repo")
    onboarded_at = channel_config.get("onboarded_at", "Unknown")
    onboarded_by = channel_config.get("onboarded_by", "Unknown")
    
    # Try to get channel name
    try:
        channel_info = client.conversations_info(channel=channel_id)
        channel_name = channel_info["channel"]["name"]
    except Exception:
        channel_name = channel_id
    
    # Format timestamp
    try:
        dt = datetime.fromisoformat(onboarded_at.replace('Z', '+00:00'))
        formatted_time = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        formatted_time = onboarded_at
    
    say(
        text=f"📊 *Channel Status*\n"
             f"━━━━━━━━━━━━━━━\n"
             f"📺 Channel: #{channel_name}\n"
             f"🔗 Repository: `{repo}`\n"
             f"⏰ Onboarded: {formatted_time}\n"
             f"👤 By: <@{onboarded_by}>",
        thread_ts=thread_ts
    )


def handle_conversation(channel_id: str, text: str, say, thread_ts: str):
    """Handle general conversation (non-command mentions)."""
    repo = get_channel_repo(channel_id)
    
    if not repo:
        say(
            text="⚠️ This channel hasn't been onboarded yet.\n"
                 "To get started: `@agent onboard repo your-org/your-repo`",
            thread_ts=thread_ts
        )
        return
    
    # v0: Just acknowledge with stub response
    say(
        text=f"I'm your agent for `{repo}`. 🤖\n\n"
             f"_(LLM integration not connected yet, but I know we're talking about {repo}!)_\n\n"
             f"You asked: _{text}_",
        thread_ts=thread_ts
    )


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Start the Slack bot."""
    # Validate environment variables
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")
    
    if not bot_token:
        logger.error("SLACK_BOT_TOKEN not found in environment variables")
        raise ValueError("Missing SLACK_BOT_TOKEN")
    
    if not app_token:
        logger.error("SLACK_APP_TOKEN not found in environment variables")
        raise ValueError("Missing SLACK_APP_TOKEN")
    
    logger.info("=" * 60)
    logger.info("Starting Slack Repo Agent...")
    logger.info(f"Bot Token: {bot_token[:20]}...")
    logger.info(f"App Token: {app_token[:20]}...")
    logger.info(f"State file: {Path(STATE_FILE).absolute()}")
    logger.info("=" * 60)
    
    # Initialize state file if it doesn't exist
    if not Path(STATE_FILE).exists():
        save_state({"channels": {}})
        logger.info(f"Created new state file: {STATE_FILE}")
    
    # Start the app
    logger.info("Initializing Socket Mode handler...")
    handler = SocketModeHandler(app, app_token)
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    logger.info("Waiting for events...")
    handler.start()


if __name__ == "__main__":
    main()
