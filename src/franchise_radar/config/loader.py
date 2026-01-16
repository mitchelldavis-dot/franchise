"""Configuration loader and manager."""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from loguru import logger


class ConfigLoader:
    """Load and manage YAML configurations."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize config loader.

        Args:
            config_path: Path to config file or directory
        """
        if config_path is None:
            # Default to config directory
            config_path = os.path.join(
                Path(__file__).parent.parent.parent.parent, "config"
            )

        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file(s)."""
        if self.config_path.is_file():
            # Load single file
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)
        elif self.config_path.is_dir():
            # Load default config
            default_config = self.config_path / "general_gym_franchise.yaml"
            if default_config.exists():
                with open(default_config) as f:
                    self.config = yaml.safe_load(f)
            else:
                logger.warning(f"No default config found at {default_config}")
                self.config = {}
        else:
            logger.warning(f"Config path not found: {self.config_path}")
            self.config = {}

        logger.info(f"Loaded configuration from {self.config_path}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def get_phrase_pack(self, pack_name: str) -> List[Dict[str, Any]]:
        """Get phrase pack by name."""
        packs = self.get("phrase_packs", {})
        return packs.get(pack_name, [])

    def get_sources(self) -> List[Dict[str, Any]]:
        """Get enabled sources."""
        return self.get("sources", {}).get("enabled", [])

    def get_weights(self) -> Dict[str, float]:
        """Get scoring weights."""
        return self.get("scoring", {}).get("weights", {})

    def get_thresholds(self) -> Dict[str, float]:
        """Get scoring thresholds."""
        return self.get("scoring", {}).get("thresholds", {})

    def get_florida_config(self) -> Dict[str, Any]:
        """Get Florida-specific configuration."""
        return self.get("geography", {})

    def get_rate_limits(self) -> Dict[str, int]:
        """Get rate limits for sources."""
        return self.get("rate_limits", {})

    def reload(self, config_path: Optional[str] = None):
        """Reload configuration."""
        if config_path:
            self.config_path = Path(config_path)
        self._load_config()


# Global config instance
_config: Optional[ConfigLoader] = None


def get_config(reload: bool = False, config_path: Optional[str] = None) -> ConfigLoader:
    """Get global config instance."""
    global _config
    if _config is None or reload:
        _config = ConfigLoader(config_path)
    return _config
