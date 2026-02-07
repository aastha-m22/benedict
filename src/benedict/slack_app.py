"""Slack App Setup

Slack Bolt app configuration and event handlers.
"""
import json
import logging
import re
import os
from slack_bolt import App
from benedict.agent import RepoAgent

logger = logging.getLogger(__name__)

# Slack app will be initialized in create_slack_app() after .env is loaded
app = None


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
            text_clean = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
            
            logger.info(f"Processing mention in channel {channel_id}")
            logger.info(f"User: {user_id}")
            logger.info(f"Cleaned text: {text_clean}")
            
            # Route based on command type
            if agent.is_onboard_command(text_clean):
                success, message = agent.handle_onboard(channel_id, user_id, text_clean)
                say(text=message, thread_ts=thread_ts)
                
            elif agent.is_status_command(text_clean):
                success, message, channel_config = agent.handle_status(channel_id)
                
                # Try to get channel name for display
                try:
                    channel_info = client.conversations_info(channel=channel_id)
                    channel_name = channel_info["channel"]["name"]
                    # Insert channel name into message
                    message = message.replace("📊 *Channel Status*", 
                                             f"📊 *Channel Status*\n📺 Channel: #{channel_name}")
                except Exception:
                    pass
                
                say(text=message, thread_ts=thread_ts)
            
            elif agent.is_update_index_command(text_clean):
                success, message = agent.handle_update_index(channel_id, user_id, text_clean)
                say(text=message, thread_ts=thread_ts)
                
            else:
                success, message = agent.handle_conversation(channel_id, text_clean, thread_ts)
                say(text=message, thread_ts=thread_ts)
                
        except Exception as e:
            logger.error(f"Error handling app_mention: {e}", exc_info=True)
            thread_ts = event.get("thread_ts") or event.get("ts")
            say(
                text="⚠️ Sorry, I encountered an error processing your request.",
                thread_ts=thread_ts
            )
    
    return app
