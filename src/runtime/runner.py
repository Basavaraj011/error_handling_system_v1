# src/runtime/runner.py
"""
Runtime Runner - Loads and executes enabled plugins
One-pass orchestration suitable for calling from a scheduler or CLI.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import yaml

from src.core.loader import PluginLoader
from src.core.registry import get_registry

# --- Optional: wire your Phase-1 building blocks here ---
# If your plugins encapsulate this, you can let them run instead.

logger = logging.getLogger(__name__)


class RuntimeRunner:
    """Manages plugin loading and execution"""

    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self.plugin_loader = PluginLoader(config_dir)
        self.registry = get_registry()

    def load_feature_config(self) -> dict:
        """Load global feature configuration (optional)"""
        features_file = self.config_dir / "features.yaml"  # fixed path bug
        try:
            with open(features_file, "r") as f:
                cfg = yaml.safe_load(f) or {}
            logger.info(f"Loaded features config from {features_file}")
            return cfg
        except Exception as e:
            logger.error(f"Failed to load features config: {e}")
            return {}

    def load_project_config(self, project_name: str) -> dict:
        """Load project-specific configuration"""
        project_file = self.config_dir / "projects" / f"{project_name}.yaml"
        try:
            with open(project_file, "r") as f:
                cfg = yaml.safe_load(f) or {}
            logger.info(f"Loaded project config: {project_name}")
            return cfg
        except Exception as e:
            logger.error(f"Failed to load project config {project_name}: {e}")
            return {}

    def is_feature_enabled(self, project_name: str, feature_name: str) -> bool:
        """Return True if a feature is enabled for the project."""
        project_config = self.load_project_config(project_name)
        feature_cfg = project_config.get("features", {}).get(feature_name, {})
        return bool(feature_cfg.get("enabled", False))

    def initialize_enabled_plugins(self, project_config: dict) -> None:
        """Initialize all enabled plugins for a project"""
        features = project_config.get("features", {})
        for feature_name, feature_config in features.items():
            if feature_config.get("enabled", False):
                module = self.plugin_loader.load_plugin(feature_name)
                if module and hasattr(module, "initialize_plugin"):
                    module.initialize_plugin(feature_config)
                    logger.info(f"Initialized plugin: {feature_name}")
