"""
Self Heal Plugin - Entry point
"""
from src.core.registry import get_registry
import logging

logger = logging.getLogger(__name__)


def initialize_plugin(config: dict) -> None:
    """Initialize the Self Heal plugin"""
    registry = get_registry()
    registry.register_feature("self_heal", config)
    logger.info("Self Heal plugin initialized")


def get_plugin_info() -> dict:
    """Get plugin metadata"""
    return {
        "name": "self_heal",
        "version": "1.0.0",
        "description": "Automatic error detection and healing with PR generation"
    }
