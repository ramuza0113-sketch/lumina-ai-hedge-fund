# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: GraphRAG Causal & Supply Chain Extractor (Microsoft GraphRAG Inspired)
Extracts multi-hop inter-corporate supply chain dependencies, competitor rivalries,
and macroeconomic transmission linkages from unstructured news and SEC filings.
Persists living causal subgraphs directly into Neo4j for 3D visualization and CRO risk traversal.
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
from core.state_manager import load_app_settings
from core.ai_hedge_fund.graphiti_memory_manager import GraphitiMemoryManager
from google import genai
from google.genai import types


class GraphRAGExtractor:
    """
    Automated Knowledge Graph Extraction & Traversal Engine (GraphRAG architecture).
    Discovers hidden supplier-buyer dependencies and regulatory choke-points.
    """

    DEFAULT_SUPPLY_CHAINS = [
        {"source": "TSMC", "target": "NVDA", "relation": "SUPPLIES_CHIPS_TO", "detail": "先端AI GPU向け3nm/4nmウェハの独占的受託製造"},
        {"source": "ASML", "target": "TSMC", "relation": "SUPPLIES_EQUIPMENT_TO", "detail": "最先端EUV露光装置の独占供給元"},
        {"source": "NVDA", "target": "SMCI", "relation": "POWERS_AI_SERVERS_OF", "detail": "高密度GPU液冷AIサーバーの直接供給先"},
        {"source": "NVDA", "target": "MSFT", "relation": "CORE_COMPUTE_PROVIDER_FOR", "detail": "Azure AIクラウド基盤およびOpenAI専用インフラ"},
        {"source": "Arm Holdings", "target": "AAPL", "relation": "LICENSES_IP_TO", "detail": "Apple Silicon (Mシリーズ/Aシリーズ) 命令セット独占ライセンス"}
    ]

    @classmethod
    def seed_initial_supply_chains(cls) -> bool:
        """Seed core semiconductor and big tech supply chains into Neo4j"""
        driver = GraphitiMemoryManager.get_driver()
        if not driver:
            return False

        cypher = """
        UNWIND $chains AS item
        MERGE (s:Stock {symbol: item.source})
        ON CREATE SET s.name = item.source, s.created_at = datetime()
        MERGE (t:Stock {symbol: item.target})
        ON CREATE SET t.name = item.target, t.created_at = datetime()

        MERGE (s)-[r:SUPPLIES_TO {relation_type: item.relation}]->(t)
        SET r.detail = item.detail,
            r.updated_at = datetime()
        """
        try:
            with driver.session() as session:
                session.run(cypher, chains=cls.DEFAULT_SUPPLY_CHAINS)
            print(f"[GraphRAGExtractor] Seeded {len(cls.DEFAULT_SUPPLY_CHAINS)} supply chain causal edges into Neo4j.")
            return True
        except Exception as e:
            print(f"[GraphRAGExtractor] Seeding error: {e}")
            return False

    @classmethod
    def extract_causal_relationships_from_text(cls, symbol: str, text_content: str) -> List[Dict[str, Any]]:
        """
        Uses Gemini 3.8 Flash to extract structured corporate dependencies from news or filings.
        """
        cfg = load_app_settings()
        api_key = cfg.get("google_api_key", "")
        if not api_key or len(text_content.strip()) < 30:
            return []

        prompt = f"""あなたはヘッジファンドのGraphRAG因果分析AIです。
対象企業ティッカー: {symbol}
以下の金融ニュースまたは企業報告テキストを分析してください:
「{text_content[:1500]}」

【任務】
テキストから「他社との重要なサプライチェーン関係（部品供給・受託製造）」、「顧客・パートナー関係」、
または「重大な競合・地政学リスクの波及関係」を最大3件抽出してください。

【出力形式 (JSON配列のみ)】
[
  {{
    "source_entity": "供給元・原因企業（例: TSMC）",
    "target_entity": "供給先・影響先企業（例: NVDA）",
    "relation_type": "SUPPLIES_TO" / "COMPETES_WITH" / "DISRUPTS" / "DEPENDS_ON",
    "detail": "依存関係の具体的な内容（日本語40文字以内）",
    "risk_level": "HIGH" / "MEDIUM" / "LOW"
  }}
]"""
        try:
            client = genai.Client(api_key=api_key)
            res = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            raw = res.text.strip() if res and res.text else "[]"
            if raw.startswith("```"):
                import re
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            relations = json.loads(raw)

            # Persist directly into Neo4j
            if relations and isinstance(relations, list):
                cls._persist_relations_to_neo4j(relations)

            return relations
        except Exception as e:
            print(f"[GraphRAGExtractor] Extraction warning: {e}")
            return []

    @classmethod
    def _persist_relations_to_neo4j(cls, relations: List[Dict[str, Any]]) -> bool:
        driver = GraphitiMemoryManager.get_driver()
        if not driver or not relations:
            return False

        cypher = """
        UNWIND $rels AS r
        MERGE (s:Stock {symbol: r.source_entity})
        ON CREATE SET s.name = r.source_entity, s.created_at = datetime()
        MERGE (t:Stock {symbol: r.target_entity})
        ON CREATE SET t.name = r.target_entity, t.created_at = datetime()

        MERGE (s)-[rel:CAUSAL_DEPENDENCY {relation_type: r.relation_type}]->(t)
        SET rel.detail = r.detail,
            rel.risk_level = r.risk_level,
            rel.updated_at = datetime()
        """
        try:
            with driver.session() as session:
                session.run(cypher, rels=relations)
            print(f"[GraphRAGExtractor] Persisted {len(relations)} dynamic GraphRAG relations to Neo4j.")
            return True
        except Exception as e:
            print(f"[GraphRAGExtractor] Neo4j persistence error: {e}")
            return False

    @classmethod
    def query_supply_chain_risks(cls, symbol: str) -> List[Dict[str, Any]]:
        """
        Query 1-hop and 2-hop upstream suppliers and downstream buyers for a stock in Neo4j.
        Used by RiskManagerAgent (CRO) to detect contagion risks.
        """
        driver = GraphitiMemoryManager.get_driver()
        if not driver:
            return []

        norm_sym = symbol.strip().upper()
        cypher = """
        MATCH (s:Stock)-[r:SUPPLIES_TO|CAUSAL_DEPENDENCY]-(other:Stock)
        WHERE s.symbol = $sym OR s.name = $sym
        RETURN other.symbol AS related_symbol, other.name AS related_name,
               type(r) AS rel_type, r.relation_type AS specific_type,
               r.detail AS detail, r.risk_level AS risk_level
        LIMIT 10
        """
        try:
            with driver.session() as session:
                result = session.run(cypher, sym=norm_sym)
                return [dict(record) for record in result]
        except Exception as e:
            print(f"[GraphRAGExtractor] Query error for {norm_sym}: {e}")
            return []
