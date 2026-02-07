 #!/usr/bin/env python3
"""
Slack Repo Agent - Main Entry Point

Composition root where all dependencies are wired together.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode import SocketModeHandler

from benedict.agent import RepoAgent
from benedict.protocols import (
    create_llm,
    create_repo_reader,
    create_semantic_indexer,
    create_conversation_repository,
)
from benedict.slack_app import create_slack_app

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Root composition - wire everything together."""
    
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
    logger.info("=" * 60)
    
    # Create LLM (optional - can be None for stub mode)
    llm = None
    try:
        llm = create_llm(provider="claude")
        logger.info("✅ LLM initialized (Claude)")
    except Exception as e:
        logger.warning(f"⚠️ LLM not available: {e}")
        logger.info("Running in stub mode (no LLM responses)")
    
    # Create repo reader (optional - can be None for stub mode)
    repo_reader = None
    try:
        repo_reader = create_repo_reader(source="local")
        logger.info("✅ Repo reader initialized (local filesystem)")
    except Exception as e:
        logger.warning(f"⚠️ Repo reader not available: {e}")
        logger.info("Running without repository access")
    
    # Create semantic indexer (optional - falls back to keyword matching if None)
    semantic_indexer = None
    try:
        semantic_indexer = create_semantic_indexer(provider="chromadb")
        logger.info("✅ Semantic indexer initialized (ChromaDB)")
    except Exception as e:
        logger.warning(f"⚠️ Semantic indexer not available: {e}")
        logger.info("Falling back to keyword-based file matching")
    
    # Create conversation repository
    state_file = "state.json"
    conversation_repository = create_conversation_repository(provider="json", state_file=state_file)
    logger.info("✅ Conversation repository initialized (JSON)")
    
    # Create agent with dependencies
    agent = RepoAgent(
        state_file=state_file,
        llm=llm,
        repo_reader=repo_reader,
        semantic_indexer=semantic_indexer,
        conversation_repository=conversation_repository
    )
    
    # Initialize state file if it doesn't exist
    if not Path("state.json").exists():
        agent.save_state({"channels": {}})
        logger.info("Created new state file: state.json")
    
    # Create and configure Slack app
    slack_app = create_slack_app(agent)
    
    # Start the app
    logger.info("Initializing Socket Mode handler...")
    handler = SocketModeHandler(slack_app, app_token)
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    logger.info("Waiting for events...")
    handler.start()


if __name__ == "__main__":
    main()
