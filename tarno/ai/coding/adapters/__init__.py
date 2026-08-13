"""Coding adapter implementations."""

from __future__ import annotations

from tarno.ai.coding.adapters.base import CodingBackend
from tarno.ai.coding.adapters.aider_adapter import AiderBackend
from tarno.ai.coding.adapters.native_agent import NativeAgentBackend

__all__ = ["CodingBackend", "AiderBackend", "NativeAgentBackend"]
