# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Langfuse Observability & Multi-Agent Tracing Layer
Tracks parallel council debates, legend analyst reasoning paths, token usage,
and CIO verdict trees with graceful no-op fallback when unconfigured.
"""

import os
import time
from typing import Dict, Any, Optional

try:
    from langfuse import Langfuse
    HAS_LANGFUSE = True
except ImportError:
    HAS_LANGFUSE = False


class LuminaLangfuseTracer:
    """
    Zero-friction Langfuse observability tracer for Lumina Hedge Fund Council.
    Automatically captures:
    - Council session parent traces
    - Individual analyst agent reasoning spans (Buffett, Soros, Burry, etc.)
    - Risk Manager red-team critique
    - CIO Lumina final synthesis & order verdict
    """

    _client: Optional[Any] = None
    _checked: bool = False

    @classmethod
    def get_client(cls) -> Optional[Any]:
        if not HAS_LANGFUSE:
            return None
        if cls._checked and cls._client is None:
            return None
        if cls._client is not None:
            return cls._client

        from core.state_manager import load_app_settings
        settings = load_app_settings()
        
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY") or settings.get("langfuse_public_key")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY") or settings.get("langfuse_secret_key")
        host = os.environ.get("LANGFUSE_HOST") or settings.get("langfuse_host", "https://cloud.langfuse.com")

        cls._checked = True
        if public_key and secret_key:
            try:
                cls._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host
                )
                print(f"[LangfuseTracer] 🛰️ Connected to Langfuse ({host})")
                return cls._client
            except Exception as e:
                print(f"[LangfuseTracer] ⚠️ Failed to initialize Langfuse: {e}")
                return None
        return None

    @classmethod
    def is_configured(cls) -> bool:
        return cls.get_client() is not None

    @classmethod
    def start_council_trace(
        cls,
        symbol: str,
        company_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Start a parent trace for an investment council debate session"""
        client = cls.get_client()
        if not client:
            return None
        try:
            trace = client.trace(
                name=f"Council_{symbol}",
                metadata={
                    "symbol": symbol,
                    "company_name": company_name,
                    **(metadata or {})
                },
                tags=["council_debate", symbol]
            )
            return trace
        except Exception as e:
            print(f"[LangfuseTracer] Warning creating trace: {e}")
            return None

    @classmethod
    def record_agent_span(
        cls,
        trace: Optional[Any],
        agent_id: str,
        agent_name: str,
        input_data: Any,
        output_data: Any,
        latency_seconds: float = 0.0,
        model_name: str = "gemini-2.5-flash"
    ):
        """Record an analyst agent's evaluation span under the parent trace"""
        if not trace:
            return
        try:
            score = output_data.get("score") if isinstance(output_data, dict) else None
            stance = output_data.get("stance") if isinstance(output_data, dict) else None
            span = trace.span(
                name=f"Agent_{agent_name}",
                input=input_data,
                output=output_data,
                metadata={
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "stance": stance,
                    "score": score,
                    "latency_sec": round(latency_seconds, 2),
                    "model": model_name
                }
            )
            span.end()
        except Exception as e:
            print(f"[LangfuseTracer] Warning recording agent span: {e}")

    @classmethod
    def record_final_verdict(
        cls,
        trace: Optional[Any],
        verdict: Dict[str, Any],
        total_latency: float = 0.0
    ):
        """Record CIO Lumina's final synthesis verdict and complete the trace"""
        if not trace:
            return
        try:
            action = verdict.get("action", "HOLD")
            score = verdict.get("confidence_score", 0)
            trace.update(
                output={
                    "action": action,
                    "confidence_score": score,
                    "reasoning": verdict.get("reasoning", ""),
                    "target_price": verdict.get("target_price"),
                    "stop_loss_price": verdict.get("stop_loss_price"),
                    "allocation_pct": verdict.get("allocation_pct")
                }
            )
            # Flush asynchronously
            client = cls.get_client()
            if client:
                client.flush()
        except Exception as e:
            print(f"[LangfuseTracer] Warning completing trace: {e}")
