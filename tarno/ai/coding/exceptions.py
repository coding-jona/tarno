"""Exceptions raised by the coding-agent subsystem."""

from __future__ import annotations


class CodingError(Exception):
    """Base class for all coding-agent errors."""


class WorkspaceNotAGitRepoError(CodingError):
    """Raised when a workspace root is not under git version control."""


class NoProviderConfiguredError(CodingError):
    """Raised when no API provider is configured for the coding backend."""


class UnsupportedProviderError(CodingError):
    """Raised when the configured coding provider is not supported."""
