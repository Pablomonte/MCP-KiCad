#!/usr/bin/env python3
"""
Test suite for configuration management (Phase 2).

Tests Settings class, environment variable loading, validators,
and platform-specific defaults.
"""

import pytest
import os
import sys
from pathlib import Path
from pydantic import ValidationError
from mcp_kicad.config import Settings, get_settings, reload_settings

# ============================================================================
# BASIC SETTINGS TESTS
# ============================================================================


def test_settings_default_values():
    """Test Settings with default values"""
    settings = Settings(
        log_to_file=False, log_to_console=False  # Disable file logging for tests
    )

    assert settings.server_name == "kicad-mcp-server"
    assert settings.kicad_version == "9.0"
    assert settings.max_concurrent_operations == 10
    assert settings.operation_timeout_seconds == 300
    assert settings.max_board_size_mm == 1000.0
    assert settings.max_components == 10000


def test_settings_custom_values():
    """Test Settings with custom values"""
    settings = Settings(
        server_name="my-server",
        kicad_version="8.0",
        max_concurrent_operations=5,
        log_to_file=False,
        log_to_console=False,
    )

    assert settings.server_name == "my-server"
    assert settings.kicad_version == "8.0"
    assert settings.max_concurrent_operations == 5


# ============================================================================
# ENVIRONMENT VARIABLE TESTS
# ============================================================================


def test_settings_from_env(monkeypatch):
    """Test Settings loads from environment variables"""
    monkeypatch.setenv("MCP_KICAD_SERVER_NAME", "env-server")
    monkeypatch.setenv("MCP_KICAD_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MCP_KICAD_MAX_CONCURRENT_OPERATIONS", "20")
    monkeypatch.setenv("MCP_KICAD_LOG_TO_FILE", "false")

    settings = Settings()

    assert settings.server_name == "env-server"
    assert settings.log_level == "DEBUG"
    assert settings.max_concurrent_operations == 20


def test_settings_env_prefix(monkeypatch):
    """Test that only MCP_KICAD_ prefixed vars are loaded"""
    monkeypatch.setenv("SERVER_NAME", "wrong")
    monkeypatch.setenv("MCP_KICAD_SERVER_NAME", "correct")
    monkeypatch.setenv("MCP_KICAD_LOG_TO_FILE", "false")

    settings = Settings()

    assert settings.server_name == "correct"


# ============================================================================
# LOG LEVEL VALIDATION TESTS
# ============================================================================


def test_log_level_validation_valid():
    """Test valid log levels"""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    for level in valid_levels:
        settings = Settings(log_level=level, log_to_file=False, log_to_console=False)
        assert settings.log_level == level.upper()


def test_log_level_validation_case_insensitive():
    """Test log level is case-insensitive"""
    settings = Settings(log_level="debug", log_to_file=False, log_to_console=False)
    assert settings.log_level == "DEBUG"


def test_log_level_validation_invalid():
    """Test invalid log level raises error"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(log_level="INVALID", log_to_file=False)

    assert "Invalid log level" in str(exc_info.value)


# ============================================================================
# PATH VALIDATION TESTS
# ============================================================================


def test_path_expansion(tmp_path, monkeypatch):
    """Test that paths are expanded and resolved"""
    monkeypatch.setenv("HOME", str(tmp_path))

    settings = Settings(
        project_path=Path("~/test"), log_to_file=False, log_to_console=False
    )

    # Path should be expanded and absolute
    assert settings.project_path.is_absolute()
    assert "~" not in str(settings.project_path)


def test_path_creation(tmp_path):
    """Test that paths are created if they don't exist"""
    new_dir = tmp_path / "new_project_dir"
    assert not new_dir.exists()

    settings = Settings(project_path=new_dir, log_to_file=False, log_to_console=False)

    # Directory should be created
    assert settings.project_path.exists()
    assert settings.project_path.is_dir()


def test_export_base_dir_default(tmp_path):
    """Test export_base_dir default value"""
    settings = Settings(project_path=tmp_path, log_to_file=False, log_to_console=False)

    # Should create exports directory
    assert "exports" in str(settings.export_base_dir)


def test_screenshot_dir_default(tmp_path):
    """Test screenshot_dir default value"""
    settings = Settings(project_path=tmp_path, log_to_file=False, log_to_console=False)

    # Should create screenshots directory
    assert "screenshots" in str(settings.screenshot_dir)


# ============================================================================
# NUMERIC RANGE VALIDATION TESTS
# ============================================================================


def test_max_concurrent_operations_range():
    """Test max_concurrent_operations range validation"""
    # Valid values
    settings = Settings(
        max_concurrent_operations=1, log_to_file=False, log_to_console=False
    )
    assert settings.max_concurrent_operations == 1

    settings = Settings(
        max_concurrent_operations=100, log_to_file=False, log_to_console=False
    )
    assert settings.max_concurrent_operations == 100

    # Invalid values
    with pytest.raises(ValidationError):
        Settings(max_concurrent_operations=0, log_to_file=False)

    with pytest.raises(ValidationError):
        Settings(max_concurrent_operations=101, log_to_file=False)


def test_operation_timeout_range():
    """Test operation_timeout_seconds range validation"""
    # Valid values
    settings = Settings(
        operation_timeout_seconds=1, log_to_file=False, log_to_console=False
    )
    assert settings.operation_timeout_seconds == 1

    # Invalid value
    with pytest.raises(ValidationError):
        Settings(operation_timeout_seconds=0, log_to_file=False)


def test_max_board_size_range():
    """Test max_board_size_mm range validation"""
    settings = Settings(
        max_board_size_mm=500.0, log_to_file=False, log_to_console=False
    )
    assert settings.max_board_size_mm == 500.0

    # Invalid value
    with pytest.raises(ValidationError):
        Settings(max_board_size_mm=5.0, log_to_file=False)  # < 10.0


def test_screenshot_dimensions_range():
    """Test screenshot dimension range validation"""
    settings = Settings(
        screenshot_width=1920,
        screenshot_height=1080,
        log_to_file=False,
        log_to_console=False,
    )
    assert settings.screenshot_width == 1920
    assert settings.screenshot_height == 1080

    # Invalid values
    with pytest.raises(ValidationError):
        Settings(screenshot_width=500, log_to_file=False)  # < 800


def test_screenshot_quality_range():
    """Test screenshot quality range validation"""
    settings = Settings(screenshot_quality=95, log_to_file=False, log_to_console=False)
    assert settings.screenshot_quality == 95

    # Invalid values
    with pytest.raises(ValidationError):
        Settings(screenshot_quality=101, log_to_file=False)


# ============================================================================
# BOOLEAN SETTINGS TESTS
# ============================================================================


def test_boolean_settings():
    """Test boolean settings"""
    settings = Settings(
        use_flatpak=True,
        create_timestamped_exports=False,
        zip_exports=True,
        enable_visual_verification=False,
        enable_undo=True,
        persist_history=True,
        allow_external_commands=True,
        enable_debug=True,
        enable_mock_mode=True,
        enable_caching=False,
        log_to_file=False,
        log_to_console=False,
    )

    assert settings.use_flatpak is True
    assert settings.create_timestamped_exports is False
    assert settings.zip_exports is True
    assert settings.enable_visual_verification is False
    assert settings.enable_undo is True
    assert settings.persist_history is True
    assert settings.allow_external_commands is True
    assert settings.enable_debug is True
    assert settings.enable_mock_mode is True
    assert settings.enable_caching is False


# ============================================================================
# PLATFORM DEFAULTS TESTS
# ============================================================================


def test_log_dir_linux(monkeypatch):
    """Test log_dir default for Linux"""
    monkeypatch.setattr(sys, "platform", "linux")

    settings = Settings(log_to_file=False, log_to_console=False)

    # Should set Linux default
    assert ".local/share/mcp-kicad/logs" in str(settings.log_dir)


def test_log_dir_custom():
    """Test custom log_dir overrides platform default"""
    custom_dir = Path("/tmp/custom_logs")
    custom_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(log_dir=custom_dir, log_to_file=False, log_to_console=False)

    assert settings.log_dir == custom_dir


# ============================================================================
# PATH SECURITY TESTS
# ============================================================================


def test_is_path_allowed_empty_whitelist(tmp_path):
    """Test is_path_allowed with empty whitelist (allow all)"""
    settings = Settings(
        allowed_project_paths=[], log_to_file=False, log_to_console=False
    )

    # Empty whitelist allows all paths
    assert settings.is_path_allowed(tmp_path)
    assert settings.is_path_allowed(Path("/tmp"))
    assert settings.is_path_allowed(Path("/home/user/projects"))


def test_is_path_allowed_with_whitelist(tmp_path):
    """Test is_path_allowed with whitelist"""
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()

    forbidden_dir = tmp_path / "forbidden"
    forbidden_dir.mkdir()

    settings = Settings(
        allowed_project_paths=[allowed_dir], log_to_file=False, log_to_console=False
    )

    # Path inside whitelist
    assert settings.is_path_allowed(allowed_dir / "project.kicad_pcb")

    # Path outside whitelist
    assert not settings.is_path_allowed(forbidden_dir / "project.kicad_pcb")


def test_is_path_allowed_nested(tmp_path):
    """Test is_path_allowed with nested paths"""
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()
    child_dir = parent_dir / "child"
    child_dir.mkdir()

    settings = Settings(
        allowed_project_paths=[parent_dir], log_to_file=False, log_to_console=False
    )

    # Nested path should be allowed
    assert settings.is_path_allowed(child_dir)
    assert settings.is_path_allowed(child_dir / "subdir" / "file.txt")


# ============================================================================
# SINGLETON TESTS
# ============================================================================


def test_get_settings_singleton():
    """Test get_settings returns singleton instance"""
    # Reset singleton (this is done by conftest.py fixture)
    from mcp_kicad import config

    config._settings = None

    settings1 = get_settings()
    settings2 = get_settings()

    # Should be the same instance
    assert settings1 is settings2


def test_reload_settings():
    """Test reload_settings creates new instance"""
    from mcp_kicad import config

    config._settings = None

    settings1 = get_settings()
    settings2 = reload_settings()

    # Should be different instances
    assert settings1 is not settings2


def test_reload_settings_picks_up_env_changes(monkeypatch):
    """Test reload_settings picks up environment changes"""
    from mcp_kicad import config

    config._settings = None

    monkeypatch.setenv("MCP_KICAD_SERVER_NAME", "server1")
    monkeypatch.setenv("MCP_KICAD_LOG_TO_FILE", "false")
    settings1 = get_settings()
    assert settings1.server_name == "server1"

    monkeypatch.setenv("MCP_KICAD_SERVER_NAME", "server2")
    settings2 = reload_settings()
    assert settings2.server_name == "server2"


# ============================================================================
# LOGGING CONFIGURATION TESTS
# ============================================================================


def test_logging_configuration():
    """Test logging-related settings"""
    settings = Settings(
        log_level="DEBUG",
        log_to_file=True,
        log_to_console=True,
        log_json=True,
        log_rotation_mb=20,
        log_retention_days=14,
    )

    assert settings.log_level == "DEBUG"
    assert settings.log_to_file is True
    assert settings.log_to_console is True
    assert settings.log_json is True
    assert settings.log_rotation_mb == 20
    assert settings.log_retention_days == 14


def test_log_rotation_range():
    """Test log rotation MB range validation"""
    settings = Settings(log_rotation_mb=1, log_to_file=False, log_to_console=False)
    assert settings.log_rotation_mb == 1

    with pytest.raises(ValidationError):
        Settings(log_rotation_mb=0, log_to_file=False)


def test_log_retention_range():
    """Test log retention days range validation"""
    settings = Settings(log_retention_days=30, log_to_file=False, log_to_console=False)
    assert settings.log_retention_days == 30

    with pytest.raises(ValidationError):
        Settings(log_retention_days=400, log_to_file=False)


# ============================================================================
# HISTORY SETTINGS TESTS
# ============================================================================


def test_history_settings():
    """Test history-related settings"""
    settings = Settings(
        max_history_size=100,
        enable_undo=True,
        persist_history=True,
        log_to_file=False,
        log_to_console=False,
    )

    assert settings.max_history_size == 100
    assert settings.enable_undo is True
    assert settings.persist_history is True
    assert "history.db" in str(settings.history_db_path)


def test_history_size_range():
    """Test max_history_size range validation"""
    settings = Settings(max_history_size=1, log_to_file=False, log_to_console=False)
    assert settings.max_history_size == 1

    with pytest.raises(ValidationError):
        Settings(max_history_size=0, log_to_file=False)

    with pytest.raises(ValidationError):
        Settings(max_history_size=201, log_to_file=False)


# ============================================================================
# PERFORMANCE SETTINGS TESTS
# ============================================================================


def test_caching_settings():
    """Test caching-related settings"""
    settings = Settings(
        enable_caching=True,
        cache_ttl_seconds=120,
        log_to_file=False,
        log_to_console=False,
    )

    assert settings.enable_caching is True
    assert settings.cache_ttl_seconds == 120


def test_cache_ttl_range():
    """Test cache_ttl_seconds range validation"""
    # 0 means no expiration
    settings = Settings(cache_ttl_seconds=0, log_to_file=False, log_to_console=False)
    assert settings.cache_ttl_seconds == 0

    # Max value
    settings = Settings(cache_ttl_seconds=3600, log_to_file=False, log_to_console=False)
    assert settings.cache_ttl_seconds == 3600

    # Out of range
    with pytest.raises(ValidationError):
        Settings(cache_ttl_seconds=3601, log_to_file=False)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_settings_complete_config(tmp_path, monkeypatch):
    """Test Settings with complete configuration"""
    monkeypatch.setenv("MCP_KICAD_SERVER_NAME", "integration-test")
    monkeypatch.setenv("MCP_KICAD_LOG_LEVEL", "WARNING")

    settings = Settings(
        project_path=tmp_path / "projects",
        kicad_version="8.0",
        max_concurrent_operations=15,
        operation_timeout_seconds=600,
        max_board_size_mm=500.0,
        max_components=5000,
        create_timestamped_exports=False,
        enable_visual_verification=True,
        enable_debug=True,
        log_to_file=False,
        log_to_console=False,
    )

    # Env vars override
    assert settings.server_name == "integration-test"
    assert settings.log_level == "WARNING"

    # Direct values
    assert settings.kicad_version == "8.0"
    assert settings.max_concurrent_operations == 15
    assert settings.operation_timeout_seconds == 600
    assert settings.max_board_size_mm == 500.0
    assert settings.max_components == 5000
    assert settings.create_timestamped_exports is False
    assert settings.enable_visual_verification is True
    assert settings.enable_debug is True
