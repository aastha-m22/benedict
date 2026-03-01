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

    # Get bot user ID for thread detection
    bot_user_id = None
    try:
        auth_response = app.client.auth_test()
        if auth_response.get("ok"):
            bot_user_id = auth_response.get("user_id")
            logger.info(f"Bot user ID: {bot_user_id}")
    except Exception as e:
        logger.warning(f"Could not get bot user ID: {e}")

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

            # Check for architect onboarding first
            if agent.is_architect_onboard_command(text_clean):
                success, message = agent.handle_onboard_architect(channel_id, user_id, text_clean)
                format_and_send_message(say, message, thread_ts, message_type="command")
                return

            # Check if this is architect channel - route to architect handler
            architect_channel = agent.get_architect_channel()
            if architect_channel == channel_id:
                # Route to architect handler (skip normal command routing)
                success, message = agent.handle_architect_query(channel_id, text_clean, thread_ts)
                if not success and "⚠️" in message:
                    format_and_send_message(say, message, thread_ts, message_type="error")
                else:
                    format_and_send_message(say, message, thread_ts, message_type="conversation")
                return

            # Route based on command type
            if agent.is_onboard_command(text_clean):
                success, message = agent.handle_onboard(channel_id, user_id, text_clean)
                format_and_send_message(say, message, thread_ts, message_type="command")

            elif agent.is_offboard_command(text_clean):
                success, message = agent.handle_offboard(channel_id, user_id)
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

            elif agent.is_create_method_command(text_clean):
                repo = agent.get_channel_repo(channel_id)
                if not repo:
                    success, message = (
                        False,
                        "⚠️ Not Onboarded\n\n"
                        "This channel hasn't been onboarded yet.\n\n"
                        "*Next steps:*\n"
                        "• Use `@agent onboard repo your-org/your-repo` to get started",
                    )
                else:
                    success, message = agent.handle_create_method(channel_id, repo)
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

    # Register message event handler for automatic background indexing and thread replies
    @app.event("message")
    def handle_message(event, say, client):
        """Handle message events for automatic background indexing and thread replies."""
        try:
            # Skip bot messages and messages without text
            if event.get("subtype") or not event.get("text"):
                return

            channel_id = event.get("channel")
            user_id = event.get("user")
            text = event.get("text", "")
            thread_ts = event.get("thread_ts")
            message_ts = event.get("ts")

            if not channel_id:
                return

            # Skip messages from the bot itself
            if bot_user_id and user_id == bot_user_id:
                return

            # Skip messages that mention the bot - app_mention handler will process those
            # Check if message contains bot mention to avoid duplicate processing
            if bot_user_id and f"<@{bot_user_id}>" in text:
                return

            # Check if channel is onboarded (regular project or architect)
            repo = agent.get_channel_repo(channel_id)
            architect_channel = agent.get_architect_channel()
            is_architect_channel = architect_channel == channel_id
            
            if not repo and not is_architect_channel:
                return  # Channel not onboarded, skip processing

            # Check if this is a thread reply where Benedict has already participated
            is_thread_reply = thread_ts is not None
            should_respond = False

            if is_thread_reply and bot_user_id:
                try:
                    # Check if bot has messages in this thread
                    thread_replies = client.conversations_replies(
                        channel=channel_id, ts=thread_ts
                    )
                    if thread_replies.get("ok"):
                        messages = thread_replies.get("messages", [])
                        # Check if bot has any messages in this thread
                        bot_has_messages = any(
                            msg.get("user") == bot_user_id for msg in messages
                        )
                        if bot_has_messages:
                            should_respond = True
                            logger.info(
                                f"Detected thread reply to Benedict in thread {thread_ts} "
                                f"in channel {channel_id}"
                            )
                except Exception as e:
                    logger.debug(f"Error checking thread for bot participation: {e}")

            # If not a thread reply, check if message seems directed at the bot
            if not should_respond and not is_thread_reply:
                if agent.is_message_directed_at_bot(text):
                    should_respond = True
                    logger.info(
                        f"Detected message directed at Benedict in channel {channel_id}: {text[:50]}..."
                    )

            # If message is directed at Benedict, handle it as a conversation
            if should_respond:
                try:
                    # Use thread_ts if in thread, otherwise use message_ts for new conversation
                    conversation_ts = thread_ts or message_ts
                    
                    # Route to architect handler if this is architect channel
                    if is_architect_channel:
                        success, message = agent.handle_architect_query(
                            channel_id, text, conversation_ts
                        )
                    else:
                        success, message = agent.handle_conversation(
                            channel_id, text, conversation_ts
                        )
                    
                    if not success and "⚠️" in message:
                        format_and_send_message(say, message, conversation_ts, message_type="error")
                    else:
                        format_and_send_message(
                            say, message, conversation_ts, message_type="conversation"
                        )
                except Exception as e:
                    logger.error(f"Error handling message directed at bot: {e}", exc_info=True)

            # Trigger background indexing of new messages
            # This runs asynchronously and doesn't block the response
            try:
                agent.index_new_slack_messages(channel_id)
            except Exception as e:
                logger.warning(
                    f"Error in background indexing for channel {channel_id}: {e}", exc_info=True
                )
                # Don't fail - background indexing errors shouldn't affect the app

        except Exception as e:
            logger.debug(f"Error handling message event: {e}")

    return app
