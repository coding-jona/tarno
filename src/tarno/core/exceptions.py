"""Domain exceptions for TARNO."""

from __future__ import annotations


class TarnoError(Exception):
    """Base class for all TARNO domain errors."""


class ConfigError(TarnoError):
    """Invalid or missing configuration."""


class ToolError(TarnoError):
    """Tool execution failed."""


class ToolNotFoundError(ToolError):
    """Requested tool is not registered."""


class CommandBlockedError(TarnoError):
    """A command was blocked by the risk/blocklist engine."""


class PermissionDeniedError(TarnoError):
    """User did not grant the required permission."""


class ProviderError(TarnoError):
    """LLM provider communication failed."""


class AudioError(TarnoError):
    """Audio subsystem error."""


class SecurityError(TarnoError):
    """Security policy violation."""
