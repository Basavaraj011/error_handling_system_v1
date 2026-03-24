"""
Dynamic plugin loader - loads enabled plugins at runtime
"""
import os
import sys
import importlib.util
from pathlib import Path
from typing import Dict, Any, Type
import logging

logger = logging.getLogger(__name__)


class PluginLoader:
    """Dynamically loads and manages plugin modules"""
    
    def __init__(self, plugins_dir: str):
        self.plugins_dir = Path(plugins_dir)
        self.loaded_plugins: Dict[str, Any] = {}
    
    def load_plugin(self, plugin_name: str) -> Any:
        """Load a single plugin by name"""
        plugin_path = self.plugins_dir / plugin_name / "plugin.py"
        
        if not plugin_path.exists():
            logger.error(f"Plugin {plugin_name} not found at {plugin_path}")
            return None
        
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_name}", 
                plugin_path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{plugin_name}"] = module
            spec.loader.exec_module(module)
            
            self.loaded_plugins[plugin_name] = module
            logger.info(f"Successfully loaded plugin: {plugin_name}")
            return module
        
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return None
    
    def load_all_plugins(self, enabled_plugins: list) -> Dict[str, Any]:
        """Load all enabled plugins"""
        loaded = {}
        for plugin_name in enabled_plugins:
            module = self.load_plugin(plugin_name)
            if module:
                loaded[plugin_name] = module
        
        return loaded
    
    def get_plugin(self, plugin_name: str) -> Any:
        """Get a previously loaded plugin"""
        return self.loaded_plugins.get(plugin_name)
