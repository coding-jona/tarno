"""Exceptions raised by the Agent-Pool subsystem."""

from __future__ import annotations


class PoolError(Exception):
    """Base class for all Agent-Pool errors."""


class InvalidPoolConfigError(PoolError):
    """Raised when a PoolConfig fails validation (agent count, lead count)."""
