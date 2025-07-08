"""Configuration management for GNOME AI Assistant."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""
    provider: str = "ollama"  # ollama, openai, anthropic
    model: str = "llama2"
    api_key: Optional[str] = None
    base_url: Optional[str] = "http://localhost:11434"
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 30


@dataclass
class ServiceConfig:
    """Configuration for the main service."""
    socket_path: str = "/tmp/gnome-ai-assistant.sock"
    host: str = "localhost"
    port: int = 8000
    reload: bool = False
    workers: int = 1
    log_level: str = "INFO"


@dataclass
class SecurityConfig:
    """Security and permission configuration."""
    require_permissions: bool = True
    default_permission_level: str = "deny"
    session_timeout: int = 3600  # 1 hour
    audit_log: bool = True
    max_concurrent_requests: int = 10


@dataclass
class DatabaseConfig:
    """Database configuration."""
    sqlite_path: str = ""
    chromadb_path: str = ""
    connection_pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30


@dataclass
class VoiceConfig:
    """Voice interface configuration."""
    enabled: bool = False
    recognition_engine: str = "speech_recognition"
    tts_engine: str = "piper"
    wake_word: str = "hey assistant"
    language: str = "en-US"


@dataclass
class NotificationConfig:
    """Notification configuration."""
    enabled: bool = True
    timeout: int = 5000  # milliseconds
    priority: str = "normal"  # low, normal, high, urgent


@dataclass
class AssistantConfig:
    """Complete configuration for the AI assistant."""
    llm: LLMConfig
    service: ServiceConfig
    security: SecurityConfig
    database: DatabaseConfig
    voice: VoiceConfig
    notifications: NotificationConfig
    
    def __post_init__(self):
        """Set default paths based on user home directory."""
        if not self.database.sqlite_path:
            data_dir = Path.home() / ".local" / "share" / "gnome-ai-assistant"
            self.database.sqlite_path = str(data_dir / "assistant.db")
            
        if not self.database.chromadb_path:
            data_dir = Path.home() / ".local" / "share" / "gnome-ai-assistant"
            self.database.chromadb_path = str(data_dir / "chromadb")


class ConfigManager:
    """Manages configuration loading, saving, and validation."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        if config_path is None:
            config_dir = Path.home() / ".config" / "gnome-ai-assistant"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "settings.json"
        
        self.config_path = Path(config_path)
        self._config: Optional[AssistantConfig] = None
    
    def load_config(self) -> AssistantConfig:
        """
        Load configuration from file or create default.
        
        Returns:
            Loaded or default configuration
        """
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                    
                # Convert nested dictionaries to dataclass instances
                config_data['llm'] = LLMConfig(**config_data.get('llm', {}))
                config_data['service'] = ServiceConfig(**config_data.get('service', {}))
                config_data['security'] = SecurityConfig(**config_data.get('security', {}))
                config_data['database'] = DatabaseConfig(**config_data.get('database', {}))
                config_data['voice'] = VoiceConfig(**config_data.get('voice', {}))
                config_data['notifications'] = NotificationConfig(**config_data.get('notifications', {}))
                
                self._config = AssistantConfig(**config_data)
                logger.info(f"Loaded configuration from {self.config_path}")
            else:
                self._config = self._create_default_config()
                self.save_config()
                logger.info(f"Created default configuration at {self.config_path}")
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
            self._config = self._create_default_config()
            
        return self._config
    
    def save_config(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self._config is None:
                logger.error("No configuration to save")
                return False
                
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dictionary for JSON serialization
            config_dict = asdict(self._config)
            
            with open(self.config_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
                
            logger.info(f"Saved configuration to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_config(self) -> AssistantConfig:
        """Get current configuration, loading if necessary."""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self._config is None:
                self.load_config()
                
            # Apply updates to the configuration
            for key, value in updates.items():
                if hasattr(self._config, key):
                    if isinstance(value, dict):
                        # Handle nested configuration updates
                        current_value = getattr(self._config, key)
                        if hasattr(current_value, '__dict__'):
                            for sub_key, sub_value in value.items():
                                if hasattr(current_value, sub_key):
                                    setattr(current_value, sub_key, sub_value)
                    else:
                        setattr(self._config, key, value)
                        
            return self.save_config()
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
    
    def _create_default_config(self) -> AssistantConfig:
        """Create default configuration."""
        return AssistantConfig(
            llm=LLMConfig(),
            service=ServiceConfig(),
            security=SecurityConfig(),
            database=DatabaseConfig(),
            voice=VoiceConfig(),
            notifications=NotificationConfig()
        )
    
    def validate_config(self) -> bool:
        """
        Validate current configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            config = self.get_config()
            
            # Validate LLM configuration
            if config.llm.provider not in ["ollama", "openai", "anthropic"]:
                logger.error(f"Invalid LLM provider: {config.llm.provider}")
                return False
                
            # Validate service configuration
            if config.service.port < 1 or config.service.port > 65535:
                logger.error(f"Invalid service port: {config.service.port}")
                return False
                
            # Validate database paths
            if config.database.sqlite_path:
                sqlite_dir = Path(config.database.sqlite_path).parent
                if not sqlite_dir.exists():
                    sqlite_dir.mkdir(parents=True, exist_ok=True)
                    
            if config.database.chromadb_path:
                chromadb_dir = Path(config.database.chromadb_path)
                if not chromadb_dir.exists():
                    chromadb_dir.mkdir(parents=True, exist_ok=True)
                    
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation error: {e}")
            return False


# Global configuration manager instance
config_manager = ConfigManager()


def get_config() -> AssistantConfig:
    """Get the global configuration instance."""
    return config_manager.get_config()


def update_config(updates: Dict[str, Any]) -> bool:
    """Update the global configuration."""
    return config_manager.update_config(updates)


def validate_config() -> bool:
    """Validate the global configuration."""
    return config_manager.validate_config()
