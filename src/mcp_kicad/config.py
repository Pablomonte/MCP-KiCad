"""
Configuration management for MCP-KiCad using Pydantic Settings.

Provides type-safe configuration with environment variable support,
validation, and sensible defaults for different platforms.
"""

from pathlib import Path
from typing import Optional, List
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys


class Settings(BaseSettings):
    """
    MCP-KiCad server configuration with environment variable support.

    All settings can be overridden via environment variables with the
    MCP_KICAD_ prefix (e.g., MCP_KICAD_LOG_LEVEL=DEBUG).

    Configuration loading order (highest priority first):
    1. Environment variables (MCP_KICAD_*)
    2. .env file
    3. Default values
    """

    model_config = SettingsConfigDict(
        env_prefix='MCP_KICAD_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Project and board settings
    project_path: Path = Field(
        default_factory=Path.cwd,
        description="Root path for KiCad projects"
    )

    board_file: Optional[Path] = Field(
        default=None,
        description="Path to specific board file to load on startup"
    )

    # KiCad integration settings
    kicad_version: str = Field(
        default="9.0",
        description="Expected KiCad version"
    )

    kicad_executable: Optional[Path] = Field(
        default=None,
        description="Path to KiCad executable (auto-detected if not specified)"
    )

    use_flatpak: bool = Field(
        default=False,
        description="Whether to use KiCad Flatpak installation"
    )

    # Server settings
    server_name: str = Field(
        default="kicad-mcp-server",
        description="MCP server name identifier"
    )

    max_concurrent_operations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of concurrent operations"
    )

    operation_timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Timeout for operations in seconds"
    )

    # Board constraints
    max_board_size_mm: float = Field(
        default=1000.0,
        ge=10.0,
        le=10000.0,
        description="Maximum board dimension in millimeters"
    )

    max_components: int = Field(
        default=10000,
        ge=1,
        le=100000,
        description="Maximum number of components per board"
    )

    # File export settings
    export_base_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "exports",
        description="Base directory for exports"
    )

    create_timestamped_exports: bool = Field(
        default=True,
        description="Add timestamps to export directory names"
    )

    zip_exports: bool = Field(
        default=True,
        description="Create ZIP archives for fabrication packages"
    )

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    log_dir: Optional[Path] = Field(
        default=None,
        description="Directory for log files (auto-detected by platform if None)"
    )

    log_to_file: bool = Field(
        default=True,
        description="Enable logging to file"
    )

    log_to_console: bool = Field(
        default=True,
        description="Enable logging to console"
    )

    log_json: bool = Field(
        default=False,
        description="Use JSON format for logs"
    )

    log_rotation_mb: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Log file size before rotation (MB)"
    )

    log_retention_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days to keep old log files"
    )

    # Visual verification settings
    enable_visual_verification: bool = Field(
        default=True,
        description="Enable screenshot capture for visual feedback"
    )

    screenshot_width: int = Field(
        default=1600,
        ge=800,
        le=4000,
        description="Screenshot width in pixels"
    )

    screenshot_height: int = Field(
        default=1200,
        ge=600,
        le=3000,
        description="Screenshot height in pixels"
    )

    screenshot_quality: int = Field(
        default=85,
        ge=1,
        le=100,
        description="Screenshot JPEG quality (1-100)"
    )

    screenshot_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "screenshots",
        description="Directory for screenshots"
    )

    # History and state management
    max_history_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of operations to keep in history"
    )

    enable_undo: bool = Field(
        default=True,
        description="Enable undo/redo functionality"
    )

    persist_history: bool = Field(
        default=False,
        description="Persist operation history to disk"
    )

    history_db_path: Path = Field(
        default_factory=lambda: Path.cwd() / ".mcp_kicad_history.db",
        description="Path to history database (SQLite)"
    )

    # Security settings
    allowed_project_paths: List[Path] = Field(
        default_factory=list,
        description="Whitelist of allowed project directories (empty = allow all)"
    )

    allow_external_commands: bool = Field(
        default=False,
        description="Allow execution of external commands"
    )

    # Development settings
    enable_debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )

    enable_mock_mode: bool = Field(
        default=False,
        description="Force mock mode even if KiCad is available"
    )

    # Performance settings
    enable_caching: bool = Field(
        default=True,
        description="Enable caching of board information"
    )

    cache_ttl_seconds: int = Field(
        default=60,
        ge=0,
        le=3600,
        description="Cache TTL in seconds (0 = no expiration)"
    )

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(valid_levels)}"
            )
        return v_upper

    @field_validator('project_path', 'export_base_dir', 'screenshot_dir')
    @classmethod
    def validate_path_exists(cls, v: Path) -> Path:
        """Ensure path is absolute and create if it doesn't exist."""
        v = v.expanduser().resolve()
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator('board_file', 'kicad_executable')
    @classmethod
    def validate_file_path(cls, v: Optional[Path]) -> Optional[Path]:
        """Validate file paths if provided."""
        if v is not None:
            v = v.expanduser().resolve()
            if not v.exists():
                raise ValueError(f"File not found: {v}")
        return v

    @model_validator(mode='after')
    def set_platform_defaults(self) -> 'Settings':
        """Set platform-specific defaults."""
        # Set log directory based on platform if not specified
        if self.log_dir is None:
            if sys.platform == 'darwin':
                # macOS
                self.log_dir = Path.home() / 'Library' / 'Logs' / 'mcp-kicad'
            elif sys.platform == 'win32':
                # Windows
                import os
                appdata = os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming')
                self.log_dir = Path(appdata) / 'mcp-kicad' / 'logs'
            else:
                # Linux/Unix
                self.log_dir = Path.home() / '.local' / 'share' / 'mcp-kicad' / 'logs'

            # Create log directory
            self.log_dir.mkdir(parents=True, exist_ok=True)

        return self

    def is_path_allowed(self, path: Path) -> bool:
        """
        Check if a path is within allowed project directories.

        Args:
            path: Path to check

        Returns:
            True if path is allowed, False otherwise
        """
        if not self.allowed_project_paths:
            # Empty list means all paths are allowed
            return True

        path = path.expanduser().resolve()
        for allowed_path in self.allowed_project_paths:
            allowed_path = allowed_path.expanduser().resolve()
            try:
                path.relative_to(allowed_path)
                return True
            except ValueError:
                continue

        return False


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance (singleton).

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment and .env file.

    Returns:
        New Settings instance
    """
    global _settings
    _settings = Settings()
    return _settings
