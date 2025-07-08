"""
Test configuration and fixtures for GNOME AI Assistant.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from typing import Generator

from src.gnome_ai_assistant.core.config import AssistantConfig
from src.gnome_ai_assistant.core.permissions import PermissionManager
from src.gnome_ai_assistant.tools.base import ToolRegistry


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def test_config(temp_dir: Path) -> AssistantConfig:
    """Provide a test configuration."""
    config = AssistantConfig()
    config.database.sqlite_path = str(temp_dir / "test.db")
    config.database.vector_db_path = str(temp_dir / "vector_db")
    config.security.audit_log_path = str(temp_dir / "audit.log")
    return config


@pytest.fixture
async def permission_manager(test_config: AssistantConfig, temp_dir: Path) -> PermissionManager:
    """Provide a test permission manager."""
    db_path = str(temp_dir / "permissions.db")
    manager = PermissionManager(db_path)
    yield manager
    await manager.cleanup()


@pytest.fixture
async def tool_registry() -> ToolRegistry:
    """Provide a test tool registry."""
    registry = ToolRegistry()
    await registry.initialize()
    return registry


@pytest.fixture
def event_loop():
    """Provide an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
