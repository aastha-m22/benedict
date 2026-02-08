"""Slack App Setup

Slack Bolt app configuration and event handlers.
"""

import json
import logging
import re
import os
from typing import Optional
from slack_bolt import App
from benedict.agent import RepoAgent
from benedict.utils import SlackFormatter, BlockKitFormatter

logger = logging.getLogger(__name__)

# Slack app will be initialized in create_slack_app() after .env is loaded
app = None


def format_and_send_message(
    say,
    message: str,
    thread_ts: Optional[str] = None,
    message_type: str = "conversation",
    use_block_kit: Optional[bool] = None,
) -> None:
    """Format and send a message to Slack.

    Handles message formatting, chunking, and Block Kit formatting based on
    message type and content.

    Args:
        say: Slack say function
        message: Message text to send
        thread_ts: Optional thread timestamp for replies
        message_type: Type of message ("conversation", "status", "error", "command")
        use_block_kit: Force Block Kit usage (auto-detect if None)
    """
    if not message:
        return

    # Format based on message type
    if message_type == "status":
        # Status messages use Block Kit with structured format
        # Parse status message format: "📊 *Title*\n━━━━━━━━━━━━━━━\n🔗 Field: value\n..."
        lines = message.split("\n")
        title = ""
        fields = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract title (first line with emoji and bold)
            if not title and ("📊" in line or "✅" in line or "⚠️" in line):
                title_match = re.search(r"[📊✅⚠️]\s*\*{1,2}(.+?)\*{1,2}", line)
                if title_match:
                    title = title_match.group(1).strip()
                elif line.startswith("📊") or line.startswith("✅") or line.startswith("⚠️"):
                    title = (
                        line.replace("📊", "")
                        .replace("✅", "")
                        .replace("⚠️", "")
                        .replace("*", "")
                        .strip()
                    )
                continue

            # Skip divider lines
            if line.startswith("━") or line.startswith("─"):
                continue

            # Extract fields (emoji + key: value format)
            field_match = re.match(r"([📊🔗⏰👤📺])\s*(.+?):\s*(.+)", line)
            if field_match:
                emoji, key, value = field_match.groups()
                # Clean up key (remove markdown)
                key = re.sub(r"\*+", "", key).strip()
                fields[key] = value.strip()
            else:
                # Try format without emoji: "Key: value"
                key_value_match = re.match(r"(.+?):\s*(.+)", line)
                if key_value_match:
                    key, value = key_value_match.groups()
                    key = re.sub(r"\*+", "", key).strip()
                    fields[key] = value.strip()

        # Determine emoji from original message
        emoji = None
        if "📊" in message:
            emoji = "📊"
        elif "✅" in message:
            emoji = "✅"
        elif "⚠️" in message:
            emoji = "⚠️"

        if title and fields:
            formatted = BlockKitFormatter.format_status_message(title, fields, emoji)
        else:
            # Fallback to regular formatting
            formatted = BlockKitFormatter.format_message(message, use_block_kit=use_block_kit)

    elif message_type == "error":
        # Error messages use Block Kit error format
        # Extract error type and message
        error_match = re.match(r"⚠️\s*(.+?)\n\n(.+)", message, re.DOTALL)
        if error_match:
            error_type = error_match.group(1).strip()
            error_msg = error_match.group(2).strip()
            # Extract next steps if present
            next_steps_match = re.search(r"Next steps?[:\n]+(.+)", error_msg, re.IGNORECASE)
            next_steps = None
            if next_steps_match:
                steps_text = next_steps_match.group(1)
                next_steps = [s.strip() for s in steps_text.split("\n") if s.strip()]
            formatted = BlockKitFormatter.format_error_message(error_type, error_msg, next_steps)
        else:
            formatted = BlockKitFormatter.format_error_message("Error", message)

    elif message_type == "command":
        # Command responses (onboard, update-index) - use Block Kit for better structure
        formatted = BlockKitFormatter.format_message(message, use_block_kit=True)

    else:
        # Conversation responses - auto-detect Block Kit usage
        formatted = BlockKitFormatter.format_message(message, use_block_kit=use_block_kit)

    # Check if message needs chunking
    if "blocks" in formatted:
        # Block Kit message - check total length
        total_text = sum(
            len(block.get("text", {}).get("text", ""))
            for block in formatted["blocks"]
            if block.get("type") == "section" and "text" in block
        )
        if total_text > SlackFormatter.MAX_MESSAGE_LENGTH:
            # Split into multiple messages
            chunks = SlackFormatter.split_message(message)
            for i, chunk in enumerate(chunks):
                chunk_formatted = BlockKitFormatter.format_message(chunk, use_block_kit=True)
                if len(chunks) > 1:
                    # Add part indicator to first chunk
                    if i == 0 and "blocks" in chunk_formatted:
                        chunk_formatted["blocks"].insert(
                            0, BlockKitFormatter.create_context(f"_Part {i + 1} of {len(chunks)}_")
                        )
                say(**chunk_formatted, thread_ts=thread_ts)
        else:
            say(**formatted, thread_ts=thread_ts)
    else:
        # Simple text message - check length
        text = formatted.get("text", "")
        if len(text) > SlackFormatter.MAX_MESSAGE_LENGTH:
            chunks = SlackFormatter.split_message(text)
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    chunk = f"_Part {i + 1} of {len(chunks)}_\n\n{chunk}"
                say(text=chunk, thread_ts=thread_ts)
        else:
            say(**formatted, thread_ts=thread_ts)


def create_slack_app(agent: RepoAgent) -> App:
    """Create and configure Slack app with agent.

    Args:
        agent: RepoAgent instance

    Returns:
        Configured Slack app
    """
    # Initialize Slack app (after .env is loaded)
    global app
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN not found in environment variables")
    app = App(token=bot_token)

    # Register event handlers
    @app.event("app_mention")
    def handle_app_mention(event, say, client):
        """Handle @mentions of the bot."""
        logger.info("=" * 60)
        logger.info("APP_MENTION EVENT RECEIVED!")
        logger.info(f"Full event: {json.dumps(event, indent=2)}")
        logger.info("=" * 60)

        try:
            channel_id = event["channel"]
            user_id = event["user"]
            text = event["text"]
            thread_ts = event.get("thread_ts") or event.get("ts")

            # Remove bot mention from text
            text_clean = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

            logger.info(f"Processing mention in channel {channel_id}")
            logger.info(f"User: {user_id}")
            logger.info(f"Cleaned text: {text_clean}")

            # Route based on command type
            if agent.is_onboard_command(text_clean):
                success, message = agent.handle_onboard(channel_id, user_id, text_clean)
                format_and_send_message(say, message, thread_ts, message_type="command")

            elif agent.is_status_command(text_clean):
                success, message, channel_config = agent.handle_status(channel_id)

                # Try to get channel name for display
                try:
                    channel_info = client.conversations_info(channel=channel_id)
                    channel_name = channel_info["channel"]["name"]
                    # Insert channel name into message
                    message = message.replace(
                        "📊 *Channel Status*", f"📊 *Channel Status*\n📺 Channel: #{channel_name}"
                    )
                except Exception:
                    pass

                format_and_send_message(say, message, thread_ts, message_type="status")

            elif agent.is_update_index_command(text_clean):
                success, message = agent.handle_update_index(channel_id, user_id, text_clean)
                format_and_send_message(say, message, thread_ts, message_type="command")

            else:
                success, message = agent.handle_conversation(channel_id, text_clean, thread_ts)
                if not success and "⚠️" in message:
                    format_and_send_message(say, message, thread_ts, message_type="error")
                else:
                    format_and_send_message(say, message, thread_ts, message_type="conversation")

        except Exception as e:
            logger.error(f"Error handling app_mention: {e}", exc_info=True)
            thread_ts = event.get("thread_ts") or event.get("ts")
            error_message = (
                f"⚠️ Error\n\nSorry, I encountered an error processing your request: {str(e)}"
            )
            format_and_send_message(say, error_message, thread_ts, message_type="error")

    return app
