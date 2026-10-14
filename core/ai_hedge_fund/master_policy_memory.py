# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Master Policy & Investment Charter Memory (mem0 Inspired)
Permanently indexes and enforces the fund owner's (Master's) core investment philosophy,
risk tolerance, and operational mandates across all AI agents (The Seven Legends + CRO + CIO).
Prevents agent drift, eliminates rogue trading, and ensures personalized alignment.
"""

import os
import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from core.state_manager import load_app_settings
from google import genai
from google.genai import types


class MasterPolicyMemory:
    """
    Long-term personalized policy memory layer (mem0 architecture).
    Maintains the 'Master Investment Charter' that sits above all agent reasoning.
    """

    DB_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "ai_hedge_fund", "master_charter.db"
    )

    DEFAULT_MANDATES = [
        {
            "mandate_id": "mandate_fib_stop_loss",
            "category": "RISK",
            "rule_text": "損切りはフィボナッチ最適値 -13.0%（買値×0.87）を絶対防壁として厳守せよ。日中ノイズによる浅い損切り狩りは厳禁。",
            "priority": "ABSOLUTE",
            "source": "マスター直接指示"
        },
        {
            "mandate_id": "mandate_market_hours",
            "category": "EXECUTION",
            "rule_text": "日本時間 22:30〜翌05:00（米国市場コアタイム）は立会時間であるため、重いバッチを止め、板監視・指値執行・CRO防衛に専念せよ。",
            "priority": "CRITICAL",
            "source": "マスター直接指示"
        },
        {
            "mandate_id": "mandate_opportunity_cost",
            "category": "R_AND_D",
            "rule_text": "機会損失を避けるため、有望な仮説は実時間で長期間待たず、過去2年Walk-Forwardバックテストで即日統計検証して実戦投入せよ。",
            "priority": "HIGH",
            "source": "マスター直接指示"
        },
        {
            "mandate_id": "mandate_veto_defense",
            "category": "DEFENSE",
            "rule_text": "CRO（最高リスク管理責任者）の絶対拒否権（VETO）を尊重し、どんなに高得点であっても集中リスクや地政学リスクがある場合は見送れ。",
            "priority": "ABSOLUTE",
            "source": "マスター直接指示"
        }
    ]

    @classmethod
    def _get_connection(cls) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS master_mandates (
                mandate_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                rule_text TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'HIGH',
                source TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
        return conn

    @classmethod
    def initialize_defaults_if_needed(cls):
        """Seed the Master Investment Charter with foundational mandates if empty"""
        conn = cls._get_connection()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM master_mandates")
                count = cur.fetchone()[0]
                if count == 0:
                    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    for m in cls.DEFAULT_MANDATES:
                        cur.execute("""
                        INSERT INTO master_mandates (mandate_id, category, rule_text, priority, source, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                        """, (m["mandate_id"], m["category"], m["rule_text"], m["priority"], m["source"], now_str, now_str))
                    print(f"[MasterPolicyMemory] Initialized {len(cls.DEFAULT_MANDATES)} foundational mandates.")
        finally:
            conn.close()

    @classmethod
    def get_active_mandates(cls) -> List[Dict[str, Any]]:
        """Retrieve all currently enforced Master Mandates"""
        cls.initialize_defaults_if_needed()
        conn = cls._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM master_mandates WHERE is_active = 1 ORDER BY CASE priority WHEN 'ABSOLUTE' THEN 1 WHEN 'CRITICAL' THEN 2 WHEN 'HIGH' THEN 3 ELSE 4 END")
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @classmethod
    def format_for_council_prompt(cls) -> str:
        """Render the Master Charter as a strict, non-negotiable markdown prompt block"""
        mandates = cls.get_active_mandates()
        if not mandates:
            return ""

        lines = [
            "============================================================",
            "🏛️【ファンドオーナー（マスター）の運用憲章・至上命題 (Master Mandates)】",
            "以下の条項はファンドオーナーによる絶対命令であり、全てのエージェントはこれに違反する判断を固く禁ずる:",
        ]
        for idx, m in enumerate(mandates, 1):
            prio_badge = f"[{m['priority']}]"
            lines.append(f"{idx}. {prio_badge} ({m['category']}): {m['rule_text']}")
        lines.append("============================================================")
        return "\n".join(lines)

    @classmethod
    def add_or_update_mandate(cls, mandate_id: str, category: str, rule_text: str, priority: str = "HIGH", source: str = "チャット指示") -> bool:
        """Add or update a master mandate"""
        conn = cls._get_connection()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("""
                INSERT INTO master_mandates (mandate_id, category, rule_text, priority, source, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(mandate_id) DO UPDATE SET
                    category = excluded.category,
                    rule_text = excluded.rule_text,
                    priority = excluded.priority,
                    source = excluded.source,
                    is_active = 1,
                    updated_at = excluded.updated_at
                """, (mandate_id, category, rule_text, priority, source, now_str, now_str))
            return True
        except Exception as e:
            print(f"[MasterPolicyMemory] Error adding mandate: {e}")
            return False
        finally:
            conn.close()

    @classmethod
    def extract_and_learn_from_chat(cls, user_message: str) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini 3.8 Flash to analyze master's user message.
        If a new core rule, preference, or constraint is identified, indexes it as a mandate.
        """
        cfg = load_app_settings()
        api_key = cfg.get("google_api_key", "")
        if not api_key or len(user_message.strip()) < 5:
            return None

        prompt = f"""あなたはヘッジファンド Lumina Capital のオーナー専属記憶エージェント（mem0）です。
以下はファンドオーナー（マスター）の発言です:
「{user_message}」

【任務】
この発言の中に、今後の投資運用、リスク管理、取引ルール、セクターの好み、運用時間などに関する
「長期的に守るべきルール・方針（運用憲章）」が含まれているか判定してください。
単なる雑談や一時的な質問の場合は「is_policy: false」としてください。

【出力形式 (JSONのみ)】
{{
  "is_policy": true または false,
  "category": "RISK" / "EXECUTION" / "STRATEGY" / "PREFERENCE" / "DEFENSE",
  "rule_text": "AIエージェント達に厳守させるべきルールの要約（簡潔な命令形・日本語・50文字以内）",
  "priority": "ABSOLUTE" / "CRITICAL" / "HIGH" / "NORMAL"
}}"""
        try:
            client = genai.Client(api_key=api_key)
            res = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            raw = res.text.strip() if res and res.text else "{}"
            if raw.startswith("```"):
                import re
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)

            if data.get("is_policy"):
                mid = f"mandate_auto_{int(time.time())}"
                cls.add_or_update_mandate(
                    mandate_id=mid,
                    category=data.get("category", "PREFERENCE"),
                    rule_text=data.get("rule_text", ""),
                    priority=data.get("priority", "HIGH"),
                    source=f"マスター発言: 『{user_message[:30]}...』"
                )
                print(f"[MasterPolicyMemory] 🧠 Learned new Master Mandate: {data.get('rule_text')}")
                return data
        except Exception as e:
            print(f"[MasterPolicyMemory] Extraction error: {e}")
        return None
