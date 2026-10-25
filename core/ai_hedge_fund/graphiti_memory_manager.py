# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Graphiti & Neo4j Temporal Knowledge Graph Memory Manager
Dynamic episodic memory engine capturing trade outcomes, macroeconomic regimes,
agent reflections, and causal relationships over time.
"""

import os
import sys
import json
import time
import uuid
import datetime
from typing import Dict, Any, List, Optional

try:
    from neo4j import GraphDatabase, Driver
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False


class GraphitiMemoryManager:
    """
    Manages the temporal knowledge graph on Neo4j for Lumina AI.
    Encapsulates schema management, trade/council episode recording,
    and temporal lesson querying for investor agents.
    """

    _driver: Optional[Any] = None
    _is_initialized: bool = False
    _connection_failed: bool = False

    @classmethod
    def get_config(cls) -> Dict[str, str]:
        """Fetch Neo4j credentials from environment or defaults"""
        uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "LuminaAI_2026_Secure")
        return {"uri": uri, "user": user, "password": password}

    @classmethod
    def get_driver(cls) -> Optional[Any]:
        """Singleton driver with lazy connection and automatic failover"""
        if not HAS_NEO4J:
            return None
        if cls._connection_failed:
            return None
        if cls._driver is not None:
            return cls._driver

        cfg = cls.get_config()
        try:
            cls._driver = GraphDatabase.driver(
                cfg["uri"],
                auth=(cfg["user"], cfg["password"]),
                connection_timeout=3.0,
                max_connection_lifetime=300
            )
            # Verify connectivity
            cls._driver.verify_connectivity()
            cls._ensure_schema()
            return cls._driver
        except Exception as e:
            cls._connection_failed = True
            print(f"[GraphitiMemoryManager] [WARNING] Neo4j connection failed ({cfg['uri']}): {e}. Gracefully falling back to local SQLite.")
            return None

    @classmethod
    def is_available(cls) -> bool:
        """Check if Neo4j graph engine is alive and operational"""
        driver = cls.get_driver()
        return driver is not None

    @classmethod
    def _ensure_schema(cls):
        """Create indexes and constraints for high-speed graph traversal"""
        if cls._is_initialized or not cls._driver:
            return
        try:
            with cls._driver.session() as session:
                # Constraints (Unique IDs)
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Stock) REQUIRE s.symbol IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (sec:Sector) REQUIRE sec.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:MacroRegime) REQUIRE m.name IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (ag:InvestorAgent) REQUIRE ag.agent_id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (ep:TradeEpisode) REQUIRE ep.episode_id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Lesson) REQUIRE l.lesson_id IS UNIQUE")
                session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (cd:CouncilDecision) REQUIRE cd.decision_id IS UNIQUE")
                
                # Indexes for temporal queries
                session.run("CREATE INDEX IF NOT EXISTS FOR (ep:TradeEpisode) ON (ep.timestamp)")
                session.run("CREATE INDEX IF NOT EXISTS FOR (cd:CouncilDecision) ON (cd.timestamp)")
            cls._is_initialized = True
        except Exception as e:
            print(f"[GraphitiMemoryManager] Schema initialization warning: {e}")

    @classmethod
    def record_trade_episode(
        cls,
        symbol: str,
        company_name: str,
        sector: str,
        outcome: str,  # 'WIN' or 'LOSS'
        realized_pnl: float,
        realized_pnl_pct: float,
        exit_rule: str,
        entry_price: float = 0.0,
        exit_price: float = 0.0,
        macro_liquidity: str = "NEUTRAL",
        reflections: Optional[List[Dict[str, Any]]] = None,
        council_dialogues: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Record a complete trade outcome episode with temporal links to:
        - The stock and its sector
        - The macroeconomic liquidity regime
        - Participating agent evaluations and subsequent reflections
        """
        driver = cls.get_driver()
        if not driver:
            return False

        episode_id = f"ep_{symbol.replace('.', '_')}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cypher = """
        // 1. Merge Stock and Sector
        MERGE (s:Stock {symbol: $symbol})
        ON CREATE SET s.name = $company_name, s.sector = $sector, s.created_at = $now_iso
        ON MATCH SET s.name = $company_name, s.sector = $sector

        MERGE (sec:Sector {name: $sector})
        MERGE (s)-[:IN_SECTOR]->(sec)

        // 2. Merge Macro Regime
        MERGE (m:MacroRegime {name: $macro_liquidity})
        ON CREATE SET m.liquidity = $macro_liquidity

        // 3. Create Trade Episode
        CREATE (ep:TradeEpisode {
            episode_id: $episode_id,
            symbol: $symbol,
            outcome: $outcome,
            pnl_amount: $realized_pnl,
            pnl_pct: $realized_pnl_pct,
            exit_rule: $exit_rule,
            entry_price: $entry_price,
            exit_price: $exit_price,
            timestamp: datetime($now_iso)
        })

        CREATE (ep)-[:INVOLVED_STOCK]->(s)
        CREATE (ep)-[:UNDER_MACRO]->(m)
        """

        try:
            with driver.session() as session:
                session.run(
                    cypher,
                    symbol=symbol,
                    company_name=company_name or symbol,
                    sector=sector or "Unknown",
                    macro_liquidity=macro_liquidity or "NEUTRAL",
                    episode_id=episode_id,
                    outcome=outcome,
                    realized_pnl=float(realized_pnl),
                    realized_pnl_pct=float(realized_pnl_pct),
                    exit_rule=exit_rule,
                    entry_price=float(entry_price),
                    exit_price=float(exit_price),
                    now_iso=now_iso
                )

                # Link reflections (Lessons) if provided
                if reflections:
                    for ref in reflections:
                        agent_id = ref.get("agent_id", "")
                        agent_name = ref.get("agent_name", agent_id)
                        text = ref.get("reflection_text", "")
                        cat = ref.get("category", "RISK_DISCIPLINE")
                        lesson_id = f"lsn_{uuid.uuid4().hex[:8]}"

                        lesson_cypher = """
                        MATCH (ep:TradeEpisode {episode_id: $episode_id})
                        MERGE (ag:InvestorAgent {agent_id: $agent_id})
                        ON CREATE SET ag.name = $agent_name

                        CREATE (l:Lesson {
                            lesson_id: $lesson_id,
                            category: $category,
                            text: $text,
                            created_at: datetime($now_iso)
                        })
                        CREATE (ep)-[:PRODUCED_LESSON]->(l)
                        CREATE (l)-[:LEARNED_BY]->(ag)
                        """
                        session.run(
                            lesson_cypher,
                            episode_id=episode_id,
                            agent_id=agent_id,
                            agent_name=agent_name,
                            lesson_id=lesson_id,
                            category=cat,
                            text=text,
                            now_iso=now_iso
                        )

                # Link entry council stances if provided
                if council_dialogues:
                    for d in council_dialogues:
                        ag_id = d.get("agent_id")
                        if not ag_id or ag_id in ("cio", "risk_manager"):
                            continue
                        ag_name = d.get("agent_name", ag_id)
                        stance = d.get("stance", "NEUTRAL")
                        score = int(d.get("score", 50))

                        eval_cypher = """
                        MATCH (ep:TradeEpisode {episode_id: $episode_id})
                        MERGE (ag:InvestorAgent {agent_id: $agent_id})
                        ON CREATE SET ag.name = $agent_name
                        CREATE (ep)-[:EVALUATED_BY {stance: $stance, score: $score}]->(ag)
                        """
                        session.run(
                            eval_cypher,
                            episode_id=episode_id,
                            agent_id=ag_id,
                            agent_name=ag_name,
                            stance=stance,
                            score=score
                        )

            print(f"[GraphitiMemoryManager] 🕸️ Successfully recorded trade episode {episode_id} for {symbol} ({outcome}) in Neo4j.")
            return True
        except Exception as e:
            print(f"[GraphitiMemoryManager] Error recording trade episode: {e}")
            return False

    @classmethod
    def record_council_decision(
        cls,
        symbol: str,
        company_name: str,
        action: str,
        action_label: str,
        confidence_score: int,
        thesis_summary: str,
        sector: Optional[str] = None,
        key_agent: Optional[str] = None,
        created_at: Optional[str] = None,
        cross_debate: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record a strategic council decision (e.g. CRO Veto or High-Conviction Buy) into Neo4j:
        - Creates a (cd:CouncilDecision) node
        - Links to (s:Stock) with [:TARGETS_STOCK]
        - Links to deciding agent (e.g. Risk Manager AI) with [:DECIDED_BY]
        - Optionally links to a (deb:DebateExchange) node if cross-debate occurred
        """
        driver = cls.get_driver()
        if not driver:
            return False

        norm_sym = symbol.strip().upper()
        if created_at:
            clean_ts = str(created_at).strip().replace(" ", "T")
            if "Z" not in clean_ts and "+" not in clean_ts:
                clean_ts += "Z"
            now_iso = clean_ts
        else:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        decision_id = f"cd_{norm_sym.replace('.', '_')}_{action.lower()}"

        is_veto = ("拒否権" in action_label) or (action.upper() == "VETO")
        agent_id = "risk_manager" if is_veto else (key_agent or "cio")
        agent_name = "Risk Manager AI (CRO)" if is_veto else "Portfolio Manager / CIO Lumina AI"

        # Check for cross-debate details
        has_debate = bool(cross_debate and cross_debate.get("occurred"))
        deb_id = f"deb_{norm_sym.replace('.', '_')}" if has_debate else ""
        bear_id = cross_debate.get("bear_agent", {}).get("agent_id", "bear") if has_debate else ""
        bear_name = cross_debate.get("bear_agent", {}).get("name", "Bear Leader") if has_debate else ""
        bull_id = cross_debate.get("bull_agent", {}).get("agent_id", "bull") if has_debate else ""
        bull_name = cross_debate.get("bull_agent", {}).get("name", "Bull Leader") if has_debate else ""
        t1_attack = cross_debate.get("turn1_attack", "") if has_debate else ""
        t2_defense = cross_debate.get("turn2_defense", "") if has_debate else ""
        init_spread = int(cross_debate.get("spread_initial", 0)) if has_debate else 0
        adj_score = int(cross_debate.get("adjusted_score", 0)) if has_debate else 0
        adj_rationale = cross_debate.get("adjustment_rationale", "") if has_debate else ""

        cypher = """
        // 1. Merge Stock and Sector
        MERGE (s:Stock {symbol: $symbol})
        ON CREATE SET s.name = $company_name, s.sector = $sector, s.created_at = $now_iso
        ON MATCH SET s.name = $company_name, s.sector = coalesce($sector, s.sector)

        WITH s
        // 2. Merge Sector if known
        FOREACH (_ IN CASE WHEN $sector IS NOT NULL AND $sector <> 'Unknown' THEN [1] ELSE [] END |
            MERGE (sec:Sector {name: $sector})
            MERGE (s)-[:IN_SECTOR]->(sec)
        )

        // 3. Merge Deciding Agent
        MERGE (ag:InvestorAgent {agent_id: $agent_id})
        ON CREATE SET ag.name = $agent_name

        // 4. Merge or Update Council Decision
        MERGE (cd:CouncilDecision {decision_id: $decision_id})
        SET cd.symbol = $symbol,
            cd.action = $action,
            cd.action_label = $action_label,
            cd.confidence_score = $confidence_score,
            cd.thesis = $thesis_summary,
            cd.is_veto = $is_veto,
            cd.timestamp = datetime($now_iso)

        MERGE (cd)-[:TARGETS_STOCK]->(s)
        MERGE (cd)-[:DECIDED_BY]->(ag)

        // 5. Merge Cross-Debate Node if occurred
        WITH cd, s
        FOREACH (_ IN CASE WHEN $has_debate = true THEN [1] ELSE [] END |
            MERGE (deb:DebateExchange {debate_id: $deb_id})
            SET deb.symbol = $symbol,
                deb.bear_name = $bear_name,
                deb.bull_name = $bull_name,
                deb.turn1_attack = $t1_attack,
                deb.turn2_defense = $t2_defense,
                deb.spread_initial = $init_spread,
                deb.adjusted_score = $adj_score,
                deb.adjustment_rationale = $adj_rationale,
                deb.timestamp = datetime($now_iso)

            MERGE (cd)-[:FEATURED_DEBATE]->(deb)
            MERGE (deb)-[:TARGETS_STOCK]->(s)

            MERGE (bear_ag:InvestorAgent {agent_id: $bear_id})
            ON CREATE SET bear_ag.name = $bear_name
            MERGE (deb)-[:ACCUSED_BY]->(bear_ag)

            MERGE (bull_ag:InvestorAgent {agent_id: $bull_id})
            ON CREATE SET bull_ag.name = $bull_name
            MERGE (deb)-[:DEFENDED_BY]->(bull_ag)
        )
        """
        try:
            with driver.session() as session:
                session.run(
                    cypher,
                    symbol=norm_sym,
                    company_name=company_name or norm_sym,
                    sector=sector or "Unknown",
                    decision_id=decision_id,
                    action=action,
                    action_label=action_label,
                    confidence_score=int(confidence_score),
                    thesis_summary=thesis_summary or "",
                    is_veto=is_veto,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    now_iso=now_iso,
                    has_debate=has_debate,
                    deb_id=deb_id,
                    bear_id=bear_id,
                    bear_name=bear_name,
                    bull_id=bull_id,
                    bull_name=bull_name,
                    t1_attack=t1_attack,
                    t2_defense=t2_defense,
                    init_spread=init_spread,
                    adj_score=adj_score,
                    adj_rationale=adj_rationale
                )
            print(f"[GraphitiMemoryManager] 🏛️ Recorded council decision {decision_id} for {norm_sym} ({action_label}) in Neo4j (Debate included: {has_debate}).")
            return True
        except Exception as e:
            print(f"[GraphitiMemoryManager] Error recording council decision: {e}")
            return False

    @classmethod
    def query_temporal_lessons(
        cls,
        symbol: str,
        sector: Optional[str] = None,
        macro_liquidity: Optional[str] = None,
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Multi-dimensional graph search for relevant lessons:
        1. Direct ticker history (past wins/losses on this exact stock)
        2. Sector peer lessons (how other stocks in this sector performed)
        3. Macro regime lessons (what happened under similar liquidity)
        """
        driver = cls.get_driver()
        if not driver:
            return []

        results = []
        try:
            with driver.session() as session:
                # 1. Direct Ticker Lessons
                q_direct = """
                MATCH (s:Stock {symbol: $symbol})<-[:INVOLVED_STOCK]-(ep:TradeEpisode)-[:PRODUCED_LESSON]->(l:Lesson)
                OPTIONAL MATCH (l)-[:LEARNED_BY]->(ag:InvestorAgent)
                RETURN 'DIRECT' AS match_type, s.symbol AS symbol, ep.outcome AS outcome,
                       ep.pnl_pct AS pnl_pct, ep.exit_rule AS exit_rule, l.category AS category,
                       l.text AS lesson_text, ag.name AS agent_name, toString(ep.timestamp) AS timestamp
                ORDER BY ep.timestamp DESC LIMIT $limit
                """
                res = session.run(q_direct, symbol=symbol, limit=limit)
                for record in res:
                    results.append(dict(record))

                # 2. Sector Lessons (if sector provided and more slots needed)
                if sector and len(results) < limit:
                    remaining = limit - len(results)
                    q_sector = """
                    MATCH (sec:Sector {name: $sector})<-[:IN_SECTOR]-(s:Stock)<-[:INVOLVED_STOCK]-(ep:TradeEpisode)-[:PRODUCED_LESSON]->(l:Lesson)
                    WHERE s.symbol <> $symbol
                    OPTIONAL MATCH (l)-[:LEARNED_BY]->(ag:InvestorAgent)
                    RETURN 'SECTOR' AS match_type, s.symbol AS symbol, ep.outcome AS outcome,
                           ep.pnl_pct AS pnl_pct, ep.exit_rule AS exit_rule, l.category AS category,
                           l.text AS lesson_text, ag.name AS agent_name, toString(ep.timestamp) AS timestamp
                    ORDER BY ep.timestamp DESC LIMIT $remaining
                    """
                    res_sec = session.run(q_sector, sector=sector, symbol=symbol, remaining=remaining)
                    for record in res_sec:
                        results.append(dict(record))

                # 3. Macro Regime Lessons (if still slots remaining)
                if macro_liquidity and len(results) < limit:
                    remaining = limit - len(results)
                    q_macro = """
                    MATCH (m:MacroRegime {name: $macro_liquidity})<-[:UNDER_MACRO]-(ep:TradeEpisode)-[:PRODUCED_LESSON]->(l:Lesson)
                    MATCH (ep)-[:INVOLVED_STOCK]->(s:Stock)
                    WHERE s.symbol <> $symbol
                    OPTIONAL MATCH (l)-[:LEARNED_BY]->(ag:InvestorAgent)
                    RETURN 'MACRO' AS match_type, s.symbol AS symbol, ep.outcome AS outcome,
                           ep.pnl_pct AS pnl_pct, ep.exit_rule AS exit_rule, l.category AS category,
                           l.text AS lesson_text, ag.name AS agent_name, toString(ep.timestamp) AS timestamp
                    ORDER BY ep.timestamp DESC LIMIT $remaining
                    """
                    res_mac = session.run(q_macro, macro_liquidity=macro_liquidity, symbol=symbol, remaining=remaining)
                    for record in res_mac:
                        results.append(dict(record))

        except Exception as e:
            print(f"[GraphitiMemoryManager] Warning during lesson query: {e}")

        return results

    @classmethod
    def get_graph_statistics(cls) -> Dict[str, int]:
        """Retrieve total node and relationship counts for dashboard monitoring"""
        driver = cls.get_driver()
        if not driver:
            return {"connected": 0, "stocks": 0, "episodes": 0, "lessons": 0, "decisions": 0, "relationships": 0}

        try:
            with driver.session() as session:
                counts = session.run("""
                RETURN
                    count { MATCH (s:Stock) } AS stocks,
                    count { MATCH (ep:TradeEpisode) } AS episodes,
                    count { MATCH (l:Lesson) } AS lessons,
                    count { MATCH (cd:CouncilDecision) } AS decisions,
                    count { MATCH (fc:TimesFmForecast) } AS forecasts,
                    count { MATCH ()-[r]->() } AS relationships
                """).single()

                if counts:
                    from core.ai_hedge_fund.forecast_tracker import ForecastTracker
                    fc_cnt = counts.get("forecasts", 0) or len(ForecastTracker.load_history())
                    return {
                        "connected": 1,
                        "stocks": counts["stocks"],
                        "episodes": counts["episodes"],
                        "lessons": counts["lessons"],
                        "decisions": counts["decisions"],
                        "forecasts": fc_cnt,
                        "relationships": counts["relationships"]
                    }
        except Exception:
            pass
        from core.ai_hedge_fund.forecast_tracker import ForecastTracker
        return {"connected": 0, "stocks": 0, "episodes": 0, "lessons": 0, "decisions": 0, "forecasts": len(ForecastTracker.load_history()), "relationships": 0}

    @classmethod
    def get_graph_visualization_data(cls, max_nodes: int = 60) -> Dict[str, Any]:
        """
        Query nodes and relationships formatted for interactive Vis.js graph rendering:
        Returns:
            {
                "nodes": [{"id": ..., "label": ..., "group": ..., "title": ...}],
                "edges": [{"from": ..., "to": ..., "label": ...}]
            }
        """
        driver = cls.get_driver()
        nodes = []
        edges = []
        seen_nodes = set()

        def ensure_stock_node(sym: str, name: str = None, sector: str = None):
            if not sym:
                return None
            nid = f"stock_{sym}"
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                sec_text = sector if sector else "市場"
                nm_text = name if name else sym
                nodes.append({
                    "id": nid,
                    "label": f"⚡ {sym}\n({sec_text})",
                    "group": "stock",
                    "title": f"【銘柄ノード】\nティッカー: {sym}\n社名: {nm_text}\nセクター: {sec_text}",
                    "color": {
                        "background": "#08253d",
                        "border": "#00f0ff",
                        "highlight": {"background": "#0c3b63", "border": "#38bdf8"}
                    },
                    "borderWidth": 3,
                    "shadow": {"enabled": True, "color": "rgba(0, 240, 255, 0.7)", "size": 16},
                    "shape": "dot",
                    "size": 28
                })
            return nid

        if not driver:
            try:
                from core.ai_hedge_fund.forecast_tracker import ForecastTracker
                for it in ForecastTracker.load_history()[:10]:
                    fc_nid = f"fc_{it['forecast_id']}"
                    sym = it.get("ticker", "UNKNOWN")
                    if fc_nid not in seen_nodes:
                        seen_nodes.add(fc_nid)
                        s_nid = ensure_stock_node(sym)
                        nodes.append({
                            "id": fc_nid,
                            "label": f"🔮 予測\n{sym} ({it.get('expected_return_pct', 0.0):+.1f}%)",
                            "group": "forecast",
                            "title": f"【🔮 Google TimesFM 時系列確率予測】\n銘柄: {sym}\n中央値: ${it.get('median_price', 0):,.2f}",
                            "color": {"background": "#2e0854", "border": "#c084fc"},
                            "shape": "diamond",
                            "size": 25
                        })
                        edges.append({
                            "from": fc_nid,
                            "to": s_nid,
                            "label": "PROJECTED_FOR",
                            "color": {"color": "#c084fc", "highlight": "#f472b6"}
                        })
            except Exception:
                pass
            return {"nodes": nodes, "edges": edges}

        try:
            with driver.session() as session:
                # 1. Fetch Stocks
                r_stocks = session.run("MATCH (s:Stock) RETURN s.symbol AS id, s.name AS name, s.sector AS sector LIMIT 60")
                for r in r_stocks:
                    ensure_stock_node(r['id'], r['name'], r['sector'])

                # 2. Fetch Sectors
                r_sec = session.run("MATCH (s:Stock)-[:IN_SECTOR]->(sec:Sector) RETURN s.symbol AS stock, sec.name AS sec LIMIT 30")
                for r in r_sec:
                    sec_id = f"sec_{r['sec']}"
                    s_nid = ensure_stock_node(r['stock'])
                    if sec_id not in seen_nodes:
                        seen_nodes.add(sec_id)
                        nodes.append({
                            "id": sec_id,
                            "label": f"🏢 {r['sec']}",
                            "group": "sector",
                            "title": f"【セクターノード】\n分類: {r['sec']}",
                            "color": {
                                "background": "#1e1338",
                                "border": "#c084fc",
                                "highlight": {"background": "#3b1e6e", "border": "#e879f9"}
                            },
                            "borderWidth": 2,
                            "shadow": {"enabled": True, "color": "rgba(192, 132, 252, 0.6)", "size": 12},
                            "shape": "box",
                            "size": 22
                        })
                    edges.append({
                        "from": s_nid,
                        "to": sec_id,
                        "label": "SECTOR",
                        "color": {"color": "rgba(192, 132, 252, 0.5)", "highlight": "#c084fc"}
                    })

                # 3. Fetch Trade Episodes
                r_eps = session.run("""
                MATCH (ep:TradeEpisode)-[:INVOLVED_STOCK]->(s:Stock)
                OPTIONAL MATCH (ep)-[:UNDER_MACRO]->(m:MacroRegime)
                RETURN ep.episode_id AS id, s.symbol AS stock, ep.outcome AS outcome,
                       ep.pnl_pct AS pnl_pct, ep.exit_rule AS exit_rule, m.name AS macro
                LIMIT 20
                """)
                for r in r_eps:
                    ep_id = f"ep_{r['id']}"
                    outcome = r["outcome"]
                    is_win = (outcome == "WIN")
                    bg = "#033b20" if is_win else "#3d081b"
                    border = "#00ff88" if is_win else "#ff0055"
                    hl_bg = "#065c32" if is_win else "#660c2d"
                    glow = "rgba(0, 255, 136, 0.75)" if is_win else "rgba(255, 0, 85, 0.75)"
                    
                    if ep_id not in seen_nodes:
                        seen_nodes.add(ep_id)
                        nodes.append({
                            "id": ep_id,
                            "label": f"{'🟢' if is_win else '🔴'} {outcome}\n{r['pnl_pct']:+.1f}%",
                            "group": "episode",
                            "title": f"【決済エピソード】\n結果: {outcome} ({r['pnl_pct']:+.1f}%)\n理由: {r['exit_rule']}",
                            "color": {
                                "background": bg,
                                "border": border,
                                "highlight": {"background": hl_bg, "border": "#ffffff"}
                            },
                            "borderWidth": 3,
                            "shadow": {"enabled": True, "color": glow, "size": 18},
                            "shape": "dot",
                            "size": 24
                        })
                    s_nid = ensure_stock_node(r['stock'])
                    edges.append({
                        "from": ep_id,
                        "to": s_nid,
                        "label": "INVOLVED",
                        "color": {"color": border, "highlight": "#ffffff"}
                    })

                # 4. Fetch Lessons and Agents
                r_lsn = session.run("""
                MATCH (ep:TradeEpisode)-[:PRODUCED_LESSON]->(l:Lesson)-[:LEARNED_BY]->(ag:InvestorAgent)
                RETURN ep.episode_id AS ep_id, l.lesson_id AS l_id, l.category AS cat,
                       l.text AS text, ag.agent_id AS ag_id, ag.name AS ag_name
                LIMIT 30
                """)
                for r in r_lsn:
                    ag_nid = f"ag_{r['ag_id']}"
                    if ag_nid not in seen_nodes:
                        seen_nodes.add(ag_nid)
                        nodes.append({
                            "id": ag_nid,
                            "label": f"👑 {r['ag_name']}",
                            "group": "agent",
                            "title": f"【伝説投資家AI】\nエージェント: {r['ag_name']}",
                            "color": {
                                "background": "#3d2503",
                                "border": "#ffb700",
                                "highlight": {"background": "#633c05", "border": "#fde047"}
                            },
                            "borderWidth": 3,
                            "shadow": {"enabled": True, "color": "rgba(255, 183, 0, 0.7)", "size": 16},
                            "shape": "diamond",
                            "size": 26
                        })

                    l_nid = f"lsn_{r['l_id']}"
                    if l_nid not in seen_nodes:
                        seen_nodes.add(l_nid)
                        nodes.append({
                            "id": l_nid,
                            "label": f"💡 {r['cat']}",
                            "group": "lesson",
                            "title": f"【獲得教訓】\n分類: {r['cat']}\n内容: {r['text']}",
                            "color": {
                                "background": "#2e2704",
                                "border": "#facc15",
                                "highlight": {"background": "#4f4306", "border": "#fef08a"}
                            },
                            "borderWidth": 2,
                            "shadow": {"enabled": True, "color": "rgba(250, 204, 21, 0.6)", "size": 12},
                            "shape": "ellipse",
                            "size": 18
                        })
                    edges.append({
                        "from": f"ep_{r['ep_id']}",
                        "to": l_nid,
                        "label": "LESSON",
                        "color": {"color": "rgba(250, 204, 21, 0.6)", "highlight": "#facc15"}
                    })
                    edges.append({
                        "from": l_nid,
                        "to": ag_nid,
                        "label": "LEARNED_BY",
                        "color": {"color": "rgba(255, 183, 0, 0.6)", "highlight": "#ffb700"}
                    })

                # 5. Fetch Strategic Council Decisions (Vetoes & High-Conviction Buys)
                r_cd = session.run("""
                MATCH (cd:CouncilDecision)-[:TARGETS_STOCK]->(s:Stock)
                OPTIONAL MATCH (cd)-[:DECIDED_BY]->(ag:InvestorAgent)
                RETURN cd.decision_id AS id, s.symbol AS symbol, cd.action AS action,
                       cd.action_label AS action_label, cd.confidence_score AS confidence,
                       cd.thesis AS thesis, cd.is_veto AS is_veto,
                       ag.agent_id AS ag_id, ag.name AS ag_name
                LIMIT 25
                """)
                for r in r_cd:
                    cd_nid = f"cd_{r['id']}"
                    act_str = str(r.get("action") or "").upper()
                    thesis = (r.get("thesis") or "").strip()
                    is_veto = bool(r.get("is_veto")) or (act_str in ("HOLD", "SELL")) or ("CRO" in thesis and "拒否" in thesis)
                    sym = r["symbol"]
                    act_label = r.get("action_label") or r.get("action")
                    conf = r.get("confidence") or 50

                    if is_veto:
                        group_name = "veto"
                        lbl = f"🛡️ CRO拒否\n{sym}"
                        title_text = f"【🚨 CROリスク管理拒否権発動】\n銘柄: {sym}\n判定: {act_label}\n確信度: {conf}点\n拒否理由: {thesis}"
                        bg = "#450a0a"
                        border = "#ff0055"
                        hl_bg = "#881337"
                        glow = "rgba(255, 0, 85, 0.85)"
                    else:
                        group_name = "decision_buy"
                        lbl = f"⚔️ 積極買\n{sym} ({conf}点)"
                        title_text = f"【⚔️ 投資委員会 買い推奨】\n銘柄: {sym}\n判定: {act_label}\n確信度: {conf}点\n論拠: {thesis}"
                        bg = "#082f49"
                        border = "#00f0ff"
                        hl_bg = "#0369a1"
                        glow = "rgba(0, 240, 255, 0.85)"

                    if cd_nid not in seen_nodes:
                        seen_nodes.add(cd_nid)
                        nodes.append({
                            "id": cd_nid,
                            "label": lbl,
                            "group": group_name,
                            "title": title_text,
                            "color": {
                                "background": bg,
                                "border": border,
                                "highlight": {"background": hl_bg, "border": "#ffffff"}
                            },
                            "borderWidth": 3,
                            "shadow": {"enabled": True, "color": glow, "size": 18},
                            "shape": "diamond" if is_veto else "box",
                            "size": 25
                        })

                    # Edge: Council Decision -> Stock
                    s_nid = ensure_stock_node(sym)
                    edges.append({
                        "from": cd_nid,
                        "to": s_nid,
                        "label": "DECIDED_ON",
                        "color": {"color": border, "highlight": "#ffffff"}
                    })

                    # Edge: Council Decision -> Deciding Agent
                    if r.get("ag_id"):
                        ag_nid = f"ag_{r['ag_id']}"
                        if ag_nid not in seen_nodes:
                            seen_nodes.add(ag_nid)
                            nodes.append({
                                "id": ag_nid,
                                "label": f"👑 {r.get('ag_name', r['ag_id'])}",
                                "group": "agent",
                                "title": f"【投資機関エージェント】\n担当: {r.get('ag_name', r['ag_id'])}",
                                "color": {
                                    "background": "#3d2503",
                                    "border": "#ffb700",
                                    "highlight": {"background": "#633c05", "border": "#fde047"}
                                },
                                "borderWidth": 3,
                                "shadow": {"enabled": True, "color": "rgba(255, 183, 0, 0.7)", "size": 16},
                                "shape": "diamond",
                                "size": 26
                            })
                        edges.append({
                            "from": cd_nid,
                            "to": ag_nid,
                            "label": "DECIDED_BY",
                            "color": {"color": "rgba(255, 183, 0, 0.6)", "highlight": "#ffb700"}
                        })

                # 6. Fetch Cross-Debates (Bull vs Bear Clash)
                r_deb = session.run("""
                MATCH (deb:DebateExchange)-[:TARGETS_STOCK]->(s:Stock)
                OPTIONAL MATCH (cd:CouncilDecision)-[:FEATURED_DEBATE]->(deb)
                RETURN deb.debate_id AS id, s.symbol AS symbol, deb.bear_name AS bear_name,
                       deb.bull_name AS bull_name, deb.turn1_attack AS attack,
                       deb.turn2_defense AS defense, deb.spread_initial AS spread,
                       deb.adjusted_score AS adj_score, deb.adjustment_rationale AS rationale,
                       cd.decision_id AS cd_id
                LIMIT 20
                """)
                for r in r_deb:
                    deb_nid = f"deb_{r['id']}"
                    sym = r["symbol"]
                    b_name = r.get("bear_name") or "Bear"
                    u_name = r.get("bull_name") or "Bull"
                    attack = (r.get("attack") or "").strip()
                    defense = (r.get("defense") or "").strip()
                    adj = r.get("adj_score") or 0
                    spread = r.get("spread") or 0
                    rat = (r.get("rationale") or "").strip()

                    title_text = (
                        f"【⚔️ 激突ディベート（対立討論）】\n"
                        f"対象銘柄: {sym} (初期スコア差: {spread}点)\n\n"
                        f"🛑 弱気派筆頭【{b_name}】の糾弾:\n「{attack}」\n\n"
                        f"🛡️ 強気派筆頭【{u_name}】の反論:\n「{defense}」\n\n"
                        f"📊 最終再評価: スコア {adj}点\n判定根拠: {rat}"
                    )

                    if deb_nid not in seen_nodes:
                        seen_nodes.add(deb_nid)
                        nodes.append({
                            "id": deb_nid,
                            "label": f"⚔️ 討論\n{b_name[:4]} vs {u_name[:4]}",
                            "group": "debate",
                            "title": title_text,
                            "color": {
                                "background": "#3b0764",
                                "border": "#f43f5e",
                                "highlight": {"background": "#581c87", "border": "#fb7185"}
                            },
                            "borderWidth": 3,
                            "shadow": {"enabled": True, "color": "rgba(244, 63, 94, 0.85)", "size": 18},
                            "shape": "hexagon",
                            "size": 26
                        })

                    # Edge: Debate -> Stock
                    s_nid = ensure_stock_node(sym)
                    edges.append({
                        "from": deb_nid,
                        "to": s_nid,
                        "label": "DEBATED",
                        "color": {"color": "#f43f5e", "highlight": "#fb7185"}
                    })

                    # Edge: Council Decision -> Debate
                    if r.get("cd_id"):
                        edges.append({
                            "from": f"cd_{r['cd_id']}",
                            "to": deb_nid,
                            "label": "TRIGGERED_DEBATE",
                            "color": {"color": "rgba(244, 63, 94, 0.6)", "highlight": "#fb7185"}
                        })

                # 7. Fetch Validated Alpha Hypotheses (Weekend Autonomous R&D)
                r_alpha = session.run("""
                MATCH (ah:AlphaHypothesis)-[:VALIDATED_ON]->(s:Stock)
                RETURN ah.hypothesis_id AS id, s.symbol AS symbol, ah.win_rate_pct AS win_rate,
                       ah.profit_factor AS pf, ah.catalyst AS catalyst, ah.grade AS grade
                LIMIT 20
                """)
                for r in r_alpha:
                    ah_nid = f"alpha_{r['id']}"
                    sym = r["symbol"]
                    wr = r.get("win_rate") or 0.0
                    pf = r.get("pf") or 0.0
                    grade = r.get("grade") or "ALPHA"
                    cat = (r.get("catalyst") or "").strip()

                    title_text = (
                        f"【💎 週末自律研究 実証済アルファ仮説】\n"
                        f"対象銘柄: {sym}\n"
                        f"格付け: {grade}\n"
                        f"過去2年バックテスト勝率: {wr:.1f}%\n"
                        f"プロフィットファクター: {pf:.2f}\n"
                        f"選定触媒: {cat}"
                    )

                    if ah_nid not in seen_nodes:
                        seen_nodes.add(ah_nid)
                        nodes.append({
                            "id": ah_nid,
                            "label": f"💎 実証アルファ\n{sym} ({wr:.0f}%)",
                            "group": "alpha",
                            "title": title_text,
                            "color": {
                                "background": "#064e3b",
                                "border": "#10b981",
                                "highlight": {"background": "#065f46", "border": "#34d399"}
                            },
                            "borderWidth": 3,
                            "shadow": {"enabled": True, "color": "rgba(16, 185, 129, 0.85)", "size": 18},
                            "shape": "star",
                            "size": 26
                        })

                    s_nid = ensure_stock_node(sym)
                    edges.append({
                        "from": ah_nid,
                        "to": s_nid,
                        "label": "PROVEN_ALPHA",
                        "color": {"color": "#10b981", "highlight": "#34d399"}
                    })

                # 8. Fetch GraphRAG Supply Chains & Causal Dependencies
                r_sc = session.run("""
                MATCH (s1:Stock)-[r]->(s2:Stock)
                RETURN s1.symbol AS src, s2.symbol AS tgt, type(r) AS rel_type,
                       r.relation_type AS specific_type, r.detail AS detail
                LIMIT 40
                """)
                for r in r_sc:
                    src_sym = r["src"]
                    tgt_sym = r["tgt"]
                    if not src_sym or not tgt_sym:
                        continue
                    s1_nid = ensure_stock_node(src_sym)
                    s2_nid = ensure_stock_node(tgt_sym)
                    rel_label = r.get("specific_type") or r.get("rel_type") or "SUPPLIES"
                    edges.append({
                        "from": s1_nid,
                        "to": s2_nid,
                        "label": rel_label,
                        "title": f"【サプライチェーン依存】\n{r.get('detail', '')}",
                        "color": {"color": "#38bdf8", "highlight": "#67e8f9"}
                    })

                # 9. Fetch TimesFM Foundation Forecasts
                r_fc = session.run("""
                MATCH (fc:TimesFmForecast)-[:FORECAST_FOR]->(s:Stock)
                OPTIONAL MATCH (cd:CouncilDecision)-[:BASED_ON_FORECAST]->(fc)
                RETURN fc.forecast_id AS id, s.symbol AS symbol, fc.target_date AS target_date,
                       fc.current_price AS base_p, fc.median_price AS med_p, fc.expected_return_pct AS ret_pct,
                       fc.lower_bound_80 AS low_80, fc.upper_bound_80 AS high_80,
                       fc.downside_risk_prob AS down_risk, fc.confidence_score AS conf,
                       fc.status AS status, cd.decision_id AS cd_id
                LIMIT 20
                """)
                for r in r_fc:
                    fc_nid = f"fc_{r['id']}"
                    sym = r["symbol"]
                    ret_pct = r.get("ret_pct") or 0.0
                    med_p = r.get("med_p") or 0.0
                    base_p = r.get("base_p") or 0.0
                    low_80 = r.get("low_80") or 0.0
                    high_80 = r.get("high_80") or 0.0
                    down_risk = r.get("down_risk") or 0.0
                    conf = r.get("conf") or 70
                    status = r.get("status") or "PENDING"
                    t_date = r.get("target_date") or ""

                    title_text = (
                        f"【🔮 Google TimesFM 時系列確率予測】\n"
                        f"対象銘柄: {sym}\n"
                        f"予測時価格: ${base_p:,.2f} ➔ 5日後中央値: ${med_p:,.2f} ({ret_pct:+.1f}%)\n"
                        f"80%想定レンジ: ${low_80:,.2f} 〜 ${high_80:,.2f}\n"
                        f"急落(-3%超)リスク確率: {down_risk:.1f}%\n"
                        f"モデル確信度: {conf}点\n"
                        f"目標期日: {t_date} (ステータス: {status})"
                    )

                    if fc_nid not in seen_nodes:
                        seen_nodes.add(fc_nid)
                        nodes.append({
                            "id": fc_nid,
                            "label": f"🔮 予測\n{sym} ({ret_pct:+.1f}%)",
                            "group": "forecast",
                            "title": title_text,
                            "color": {
                                "background": "#2e0854",
                                "border": "#c084fc",
                                "highlight": {"background": "#4c1d95", "border": "#f472b6"}
                            },
                            "borderWidth": 3,
                            "shadow": {"enabled": True, "color": "rgba(192, 132, 252, 0.85)", "size": 18},
                            "shape": "diamond",
                            "size": 25
                        })

                    s_nid = ensure_stock_node(sym)
                    edges.append({
                        "from": fc_nid,
                        "to": s_nid,
                        "label": "PROJECTED_FOR",
                        "color": {"color": "#c084fc", "highlight": "#f472b6"}
                    })

                    if r.get("cd_id"):
                        edges.append({
                            "from": f"cd_{r['cd_id']}",
                            "to": fc_nid,
                            "label": "BASED_ON_FORECAST",
                            "color": {"color": "rgba(192, 132, 252, 0.7)", "highlight": "#ffffff"}
                        })

        except Exception as e:
            print(f"[GraphitiMemoryManager] Vis data error: {e}")

        # Fallback / Local sync from ForecastTracker
        try:
            from core.ai_hedge_fund.forecast_tracker import ForecastTracker
            for it in ForecastTracker.load_history()[:10]:
                fc_nid = f"fc_{it['forecast_id']}"
                sym = it.get("ticker", "UNKNOWN")
                if fc_nid not in seen_nodes:
                    seen_nodes.add(fc_nid)
                    ret_pct = it.get("expected_return_pct", 0.0)
                    med_p = it.get("median_price", 0.0)
                    base_p = it.get("base_price", 0.0)
                    low_80 = it.get("lower_bound_80", 0.0)
                    high_80 = it.get("upper_bound_80", 0.0)
                    down_risk = it.get("downside_risk_prob", 0.0)
                    conf = it.get("confidence_score", 70)
                    status = it.get("status", "PENDING")
                    t_date = it.get("target_date", "")

                    title_text = (
                        f"【🔮 Google TimesFM 時系列確率予測】\n"
                        f"対象銘柄: {sym}\n"
                        f"予測時価格: ${base_p:,.2f} ➔ 5日後中央値: ${med_p:,.2f} ({ret_pct:+.1f}%)\n"
                        f"80%想定レンジ: ${low_80:,.2f} 〜 ${high_80:,.2f}\n"
                        f"急落(-3%超)リスク確率: {down_risk:.1f}%\n"
                        f"モデル確信度: {conf}点\n"
                        f"目標期日: {t_date} (ステータス: {status})"
                    )
                    nodes.append({
                        "id": fc_nid,
                        "label": f"🔮 予測\n{sym} ({ret_pct:+.1f}%)",
                        "group": "forecast",
                        "title": title_text,
                        "color": {
                            "background": "#2e0854",
                            "border": "#c084fc",
                            "highlight": {"background": "#4c1d95", "border": "#f472b6"}
                        },
                        "borderWidth": 3,
                        "shadow": {"enabled": True, "color": "rgba(192, 132, 252, 0.85)", "size": 18},
                        "shape": "diamond",
                        "size": 25
                    })
                    s_nid = ensure_stock_node(sym)
                    edges.append({
                        "from": fc_nid,
                        "to": s_nid,
                        "label": "PROJECTED_FOR",
                        "color": {"color": "#c084fc", "highlight": "#f472b6"}
                    })
        except Exception:
            pass

        return {"nodes": nodes, "edges": edges}

    @classmethod
    def record_alpha_hypothesis(
        cls,
        symbol: str,
        win_rate_pct: float,
        profit_factor: float,
        catalyst: str,
        confidence_grade: str = "ALPHA_PROVEN",
        conviction_score: int = 80
    ) -> bool:
        """
        Record a statistically validated Alpha Hypothesis generated by the Weekend Research Lab into Neo4j.
        Links (ah:AlphaHypothesis) -> [:VALIDATED_ON] -> (s:Stock).
        """
        driver = cls.get_driver()
        if not driver:
            return False

        norm_sym = symbol.strip().upper()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        hypo_id = f"hypo_{norm_sym}_{int(time.time())}"

        cypher = """
        MERGE (s:Stock {symbol: $symbol})
        MERGE (ah:AlphaHypothesis {hypothesis_id: $hypo_id})
        SET ah.symbol = $symbol,
            ah.win_rate_pct = $win_rate_pct,
            ah.profit_factor = $profit_factor,
            ah.catalyst = $catalyst,
            ah.grade = $confidence_grade,
            ah.conviction_score = $conviction_score,
            ah.timestamp = datetime($now_iso)

        MERGE (ah)-[:VALIDATED_ON]->(s)
        """
        try:
            with driver.session() as session:
                session.run(
                    cypher,
                    symbol=norm_sym,
                    hypo_id=hypo_id,
                    win_rate_pct=float(win_rate_pct),
                    profit_factor=float(profit_factor),
                    catalyst=catalyst or "",
                    confidence_grade=confidence_grade,
                    conviction_score=int(conviction_score),
                    now_iso=now_iso
                )
            print(f"[GraphitiMemoryManager] 💎 Recorded Alpha Hypothesis for {norm_sym} (WinRate: {win_rate_pct}%, PF: {profit_factor}) in Neo4j.")
            return True
        except Exception as e:
            print(f"[GraphitiMemoryManager] Error recording alpha hypothesis: {e}")
            return False

    @classmethod
    def record_timesfm_forecast(
        cls,
        forecast_data: Dict[str, Any],
        decision_id: Optional[str] = None
    ) -> str:
        """
        Google TimesFM 確率予測をNeo4jとForecastTrackerに永続化記録する
        """
        from core.ai_hedge_fund.forecast_tracker import ForecastTracker
        fc_id = ForecastTracker.record_forecast(forecast_data, triggered_by="council" if decision_id else "lab")

        driver = cls.get_driver()
        if not driver:
            return fc_id

        try:
            ticker = forecast_data.get("ticker", "").strip().upper()
            with driver.session() as session:
                cypher = """
                MERGE (s:Stock {symbol: $ticker})
                MERGE (fc:TimesFmForecast {forecast_id: $fc_id})
                SET fc.ticker = $ticker,
                    fc.target_date = $target_date,
                    fc.current_price = $curr_p,
                    fc.median_price = $med_p,
                    fc.expected_return_pct = $ret_pct,
                    fc.lower_bound_80 = $low_80,
                    fc.upper_bound_80 = $high_80,
                    fc.downside_risk_prob = $down_risk,
                    fc.confidence_score = $conf,
                    fc.status = $status,
                    fc.created_at = datetime()
                MERGE (fc)-[:FORECAST_FOR]->(s)
                """
                session.run(cypher, {
                    "ticker": ticker,
                    "fc_id": fc_id,
                    "target_date": forecast_data.get("target_date", ""),
                    "curr_p": float(forecast_data.get("current_price", 0.0)),
                    "med_p": float(forecast_data.get("median_price", 0.0)),
                    "ret_pct": float(forecast_data.get("expected_return_pct", 0.0)),
                    "low_80": float(forecast_data.get("lower_bound_80", 0.0)),
                    "high_80": float(forecast_data.get("upper_bound_80", 0.0)),
                    "down_risk": float(forecast_data.get("downside_risk_prob", 0.0)),
                    "conf": int(forecast_data.get("confidence_score", 70)),
                    "status": "PENDING"
                })

                if decision_id:
                    session.run("""
                    MATCH (cd:CouncilDecision {decision_id: $cd_id})
                    MATCH (fc:TimesFmForecast {forecast_id: $fc_id})
                    MERGE (cd)-[:BASED_ON_FORECAST]->(fc)
                    """, {"cd_id": decision_id, "fc_id": fc_id})
            print(f"[GraphitiMemoryManager] 🔮 Recorded TimesFM Forecast for {ticker} ({fc_id}) in Neo4j.")
        except Exception as e:
            print(f"[GraphitiMemoryManager] TimesFM Forecast Neo4j save error: {e}")

        return fc_id

    @classmethod
    def record_dual_quantum_and_meta_nodes(
        cls,
        ticker: str,
        dual_quantum: Dict[str, Any],
        lightgbm_gate: Optional[Dict[str, Any]] = None,
        lead_lag_data: Optional[Dict[str, Any]] = None,
        decision_id: Optional[str] = None
    ) -> bool:
        """
        Record DualQuantumForecast, MetaScoreModel (LightGBM), and LeadLagRelation into Neo4j
        """
        driver = cls.get_driver()
        if not driver:
            return False

        try:
            clean_sym = ticker.strip().upper()
            dq_id = f"dq_{clean_sym}_{int(time.time())}"
            lgb_id = f"lgb_{clean_sym}_{int(time.time())}"
            ll_id = f"ll_{clean_sym}_{int(time.time())}"

            with driver.session() as session:
                # 1. DualQuantumForecast Node
                cypher_dq = """
                MERGE (s:Stock {symbol: $ticker})
                CREATE (dq:DualQuantumForecast {
                    dq_id: $dq_id,
                    ticker: $ticker,
                    consensus_status: $status,
                    consensus_badge: $badge,
                    ensemble_expected_return_pct: $ret,
                    ensemble_median_price: $med,
                    confidence_score: $conf,
                    avg_downside_risk_prob: $down_risk,
                    avg_upside_breakout_prob: $up_risk,
                    created_at: datetime()
                })
                MERGE (dq)-[:FORECAST_FOR]->(s)
                """
                session.run(cypher_dq, {
                    "ticker": clean_sym,
                    "dq_id": dq_id,
                    "status": dual_quantum.get("consensus_status", "NEUTRAL"),
                    "badge": dual_quantum.get("consensus_badge", ""),
                    "ret": float(dual_quantum.get("ensemble_expected_return_pct", 0.0)),
                    "med": float(dual_quantum.get("ensemble_median_price", 0.0)),
                    "conf": int(dual_quantum.get("confidence_score", 70)),
                    "down_risk": float(dual_quantum.get("avg_downside_risk_prob", 15.0)),
                    "up_risk": float(dual_quantum.get("avg_upside_breakout_prob", 15.0))
                })

                # 2. LightGBM MetaScoreModel Node
                if lightgbm_gate:
                    cypher_lgb = """
                    MATCH (s:Stock {symbol: $ticker})
                    CREATE (m:MetaScoreModel {
                        lgb_id: $lgb_id,
                        win_probability: $win_prob,
                        gate_decision: $gate_dec,
                        gate_badge: $gate_badge,
                        top_drivers: $drivers,
                        created_at: datetime()
                    })
                    MERGE (m)-[:EVALUATES]->(s)
                    """
                    session.run(cypher_lgb, {
                        "ticker": clean_sym,
                        "lgb_id": lgb_id,
                        "win_prob": float(lightgbm_gate.get("win_probability", 50.0)),
                        "gate_dec": lightgbm_gate.get("gate_decision", "STANDARD_PASS"),
                        "gate_badge": lightgbm_gate.get("gate_badge", ""),
                        "drivers": json.dumps(lightgbm_gate.get("top_drivers", []))
                    })

                # 3. LeadLagRelation Node
                if lead_lag_data:
                    cypher_ll = """
                    MATCH (s:Stock {symbol: $ticker})
                    MERGE (bm:MacroBenchmark {symbol: $bm_sym})
                    SET bm.name = $bm_name
                    CREATE (ll:LeadLagRelation {
                        ll_id: $ll_id,
                        optimal_lag_days: $lag_days,
                        correlation: $corr,
                        granger_pvalue: $p_val,
                        signal: $sig,
                        signal_badge: $badge,
                        created_at: datetime()
                    })
                    MERGE (bm)-[:LEADS {lag_days: $lag_days, correlation: $corr}]->(s)
                    MERGE (ll)-[:COUPLES]->(s)
                    """
                    session.run(cypher_ll, {
                        "ticker": clean_sym,
                        "bm_sym": lead_lag_data.get("benchmark_symbol", "^GSPC"),
                        "bm_name": lead_lag_data.get("benchmark_name", "Global Benchmark"),
                        "ll_id": ll_id,
                        "lag_days": int(lead_lag_data.get("optimal_lag_days", 1)),
                        "corr": float(lead_lag_data.get("correlation", 0.0)),
                        "p_val": float(lead_lag_data.get("granger_pvalue", 0.05)),
                        "sig": lead_lag_data.get("lead_lag_signal", "NEUTRAL"),
                        "badge": lead_lag_data.get("signal_badge", "")
                    })

                if decision_id:
                    session.run("""
                    MATCH (cd:CouncilDecision {decision_id: $cd_id})
                    MATCH (dq:DualQuantumForecast {dq_id: $dq_id})
                    MERGE (cd)-[:BASED_ON_DUAL_QUANTUM]->(dq)
                    """, {"cd_id": decision_id, "dq_id": dq_id})

            print(f"[GraphitiMemoryManager] 🧬 Successfully persisted DualQuantum, LightGBM, and LeadLag nodes for {clean_sym} in Neo4j.")
            return True
        except Exception as e:
            print(f"[GraphitiMemoryManager] DualQuantum & Meta nodes Neo4j save error: {e}")
            return False

    @classmethod
    def record_alpha158_scan(cls, scan_result: Dict[str, Any]) -> bool:
        """
        Alpha158 全市場スクリーニング結果をNeo4jナレッジグラフに永続化
        (:Alpha158Scan)-[:TOP_ALPHA_PICK {rank, alpha_score, win_prob}]->(:Stock)
        """
        driver = cls.get_driver()
        if not driver:
            return False

        try:
            market = scan_result.get("market", "ALL")
            scan_time = scan_result.get("scan_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            scan_id = f"alpha158_scan_{int(time.time())}_{market}"
            u_size = int(scan_result.get("universe_size", 0))
            duration = float(scan_result.get("scan_duration_sec", 0.0))
            top_alphas = scan_result.get("top_alphas", [])

            with driver.session() as session:
                session.run("""
                CREATE (scan:Alpha158Scan {
                    scan_id: $scan_id,
                    market: $market,
                    scan_time: $scan_time,
                    universe_size: $u_size,
                    duration_sec: $duration,
                    created_at: datetime()
                })
                """, {
                    "scan_id": scan_id,
                    "market": market,
                    "scan_time": scan_time,
                    "u_size": u_size,
                    "duration": duration
                })

                for rank, stock in enumerate(top_alphas, 1):
                    session.run("""
                    MATCH (scan:Alpha158Scan {scan_id: $scan_id})
                    MERGE (s:Stock {symbol: $ticker})
                    ON CREATE SET s.name = $name, s.sector = $sector
                    CREATE (scan)-[:TOP_ALPHA_PICK {
                        rank: $rank,
                        alpha_score: $alpha_score,
                        win_probability: $win_prob,
                        gate_decision: $gate_dec,
                        roc5_pct: $roc5,
                        roc20_pct: $roc20,
                        trend_r2: $r2,
                        drivers: $drivers
                    }]->(s)
                    """, {
                        "scan_id": scan_id,
                        "ticker": stock["ticker"],
                        "name": stock["name"],
                        "sector": stock["sector"],
                        "rank": rank,
                        "alpha_score": float(stock["alpha_score"]),
                        "win_prob": float(stock["win_probability"]),
                        "gate_dec": stock["gate_decision"],
                        "roc5": float(stock["roc5_pct"]),
                        "roc20": float(stock["roc20_pct"]),
                        "r2": float(stock["trend_r2"]),
                        "drivers": json.dumps(stock.get("top_drivers", []))
                    })

            print(f"[GraphitiMemoryManager] 🏆 Successfully persisted Alpha158Scan ({market}, {len(top_alphas)} picks) in Neo4j.")
            return True
        except Exception as e:
            print(f"[GraphitiMemoryManager] Alpha158Scan Neo4j save error: {e}")
            return False




