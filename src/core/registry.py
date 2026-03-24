"""
Dynamic feature registry - manages enabled features
"""
from typing import Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)


class FeatureRegistry:
    """Registry for managing enabled features and their handlers"""
    
    def __init__(self):
        self.features: Dict[str, Dict[str, Any]] = {}
        self.handlers: Dict[str, list] = {}
    
    def register_feature(self, feature_name: str, config: Dict[str, Any]) -> None:
        """Register a new feature with its configuration"""
        self.features[feature_name] = config
        self.handlers[feature_name] = []
        logger.info(f"Registered feature: {feature_name}")
    
    def register_handler(self, feature_name: str, handler: Callable) -> None:
        """Register a handler for a feature"""
        if feature_name not in self.handlers:
            self.handlers[feature_name] = []
        
        self.handlers[feature_name].append(handler)
        logger.info(f"Registered handler for feature: {feature_name}")
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled"""
        if feature_name not in self.features:
            return False
        return self.features[feature_name].get("enabled", False)
    
    def get_feature_config(self, feature_name: str) -> Dict[str, Any]:
        """Get configuration for a feature"""
        return self.features.get(feature_name, {})
    
    def get_handlers(self, feature_name: str) -> list:
        """Get all handlers for a feature"""
        return self.handlers.get(feature_name, [])
    
    def list_enabled_features(self) -> list:
        """List all enabled features"""
        return [
            name for name, config in self.features.items()
            if config.get("enabled", False)
        ]


# Global registry instance
_global_registry = None


def get_registry() -> FeatureRegistry:
    """Get the global feature registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = FeatureRegistry()
    return _global_registry
