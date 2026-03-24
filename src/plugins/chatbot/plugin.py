"""
Chatbot Plugin - Entry point
"""
from src.core.registry import get_registry
import logging

logger = logging.getLogger(__name__)


def initialize_plugin(config: dict) -> None:
    """Initialize the Chatbot plugin"""
    registry = get_registry()
    registry.register_feature("chatbot", config)
    logger.info("Chatbot plugin initialized")


def get_plugin_info() -> dict:
    """Get plugin metadata"""
    return {
        "name": "chatbot",
        "version": "1.0.0",
        "description": "Interactive chatbot for error resolution and knowledge base"
    }
