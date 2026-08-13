"""TARNO Kontext-Effizienz: Tool-Output-Kompression und Verlauf-Zusammenfassung.

Reduziert, wie viel Roh-Text (Tool-/Kommandoausgaben, alte Chat-Historie)
bei jeder LLM-Anfrage erneut mitgeschickt wird - RTK-inspiriert
(github.com/rtk-ai/rtk) fuer Tool-Output, siehe output_compressor.py.
"""

from __future__ import annotations

from tarno.ai.context.output_compressor import CompressionResult, CompressorConfig, compress_tool_output
from tarno.ai.context.summarizer import HistorySummarizer
from tarno.ai.context.usage_tracker import ContextUsageTracker

__all__ = [
    "CompressionResult",
    "CompressorConfig",
    "compress_tool_output",
    "ContextUsageTracker",
    "HistorySummarizer",
]
