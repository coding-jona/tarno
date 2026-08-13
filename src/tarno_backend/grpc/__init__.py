"""gRPC bridge for the TARNO WinUI 3 frontend."""

from __future__ import annotations

import sys

# Das generierte _grpc-Modul importiert das pb2-Modul absolut als
# "tarno_pb2". In PyInstaller-Builds ist dieser Name nicht verfügbar,
# deshalb wird es als Alias in sys.modules eingetragen.
import tarno_backend.grpc.tarno_pb2 as _tarno_pb2
sys.modules["tarno_pb2"] = _tarno_pb2

from tarno_backend.grpc.tarno_pb2 import (
    AutonomyModeUpdate,
    ChatInput,
    ChatMessage,
    ClientMessage,
    CommandRequest,
    ContextUsage,
    Empty,
    LogEntry,
    PermissionRequest,
    PermissionResponse,
    ServerMessage,
    SetAutonomyMode,
    SetVisionEnabled,
    SpeechEnvelopeUpdate,
    StatusUpdate,
    SystemInfo,
    TaskUpdate,
    ThinkingUpdate,
    VisionImageAttachment,
    VisionStatusUpdate,
    VoiceCommand,
    VoiceState,
    VoiceStateUpdate,
    Workspace,
    WorkspaceFolder,
)
from tarno_backend.grpc.tarno_pb2_grpc import TarnoServicer, TarnoStub, add_TarnoServicer_to_server

__all__ = [
    "TarnoServicer",
    "TarnoStub",
    "add_TarnoServicer_to_server",
    "AutonomyModeUpdate",
    "ChatInput",
    "ChatMessage",
    "ClientMessage",
    "CommandRequest",
    "ContextUsage",
    "Empty",
    "LogEntry",
    "PermissionRequest",
    "PermissionResponse",
    "ServerMessage",
    "SetAutonomyMode",
    "SetVisionEnabled",
    "SpeechEnvelopeUpdate",
    "StatusUpdate",
    "SystemInfo",
    "TaskUpdate",
    "ThinkingUpdate",
    "VisionImageAttachment",
    "VisionStatusUpdate",
    "VoiceCommand",
    "VoiceState",
    "VoiceStateUpdate",
    "Workspace",
    "WorkspaceFolder",
]
