# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Real-Time Discord Notification Dispatcher
Sends rich embeds for:
1. Automated Buy Orders (with target & stop loss)
2. Take-Profit Executions (Partial +10%, Trailing Stop Peak-out, CIO Full Target)
3. Risk Stop-Loss Executions
4. Breaking News Catalyst Stock Discoveries
5. Council Meeting Verdict Digests
Supports both Discord Bot Token REST API and Discord Webhook URLs.
"""

import os
import json
import datetime
import urllib.request
from typing import Dict, Any, List, Optional
from core.state_manager import get_discord_settings, load_app_settings

class HedgeFundNotifier:
    """Discord Push Notification Dispatcher for Autonomous Trading"""

    @classmethod
    def _send_payload(cls, payload: Dict[str, Any]) -> bool:
        """Send Discord message via Bot Token REST API or Webhook URL safely"""
        try:
            cfg = get_discord_settings()
            token = cfg.get("bot_token", "").strip()
            channel_id = cfg.get("channel_id", "").strip()
            webhook_url = cfg.get("webhook_url", "").strip()

            # 1. Try Discord Bot REST API if token & channel_id exist
            if token and channel_id:
                url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
                headers = {
                    "Authorization": f"Bot {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "Lumina-AI-Hedge-Fund/3.5"
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 201):
                        return True

            # 2. Try Webhook URL as fallback or primary
            if webhook_url:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Lumina-AI-Hedge-Fund/3.5"
                }
                req = urllib.request.Request(webhook_url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 204):
                        return True

            return False
        except Exception as e:
            print(f"[HedgeFundNotifier] Notification dispatch error: {e}")
            return False

    @classmethod
    def notify_trade(
        cls,
        symbol: str,
        company_name: str,
        side: str,
        quantity: int,
        price: float,
        currency: str,
        rule_type: str,
        pnl_amount: float = 0.0,
        pnl_pct: float = 0.0,
        notes: str = "",
        target_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None
    ) -> bool:
        """
        Send rich embed for Buy / Sell trade executions.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        side_upper = side.upper()

        if side_upper == "BUY":
            color = 0x10b981  # Emerald Green
            title = f"🟢 【自律買い執行】{company_name} ({symbol})"
            desc = f"AI投資合議委員会による審査を通過し、新規ポジションを約定しました。\n**約定内容: {quantity:,}株 @ {price:,.2f} {currency}**"
            fields = [
                {"name": "🎯 目標株価", "value": f"{target_price:,.2f} {currency}" if target_price else "設定なし", "inline": True},
                {"name": "🛡️ 損切りライン", "value": f"{stop_loss_price:,.2f} {currency}" if stop_loss_price else "設定なし", "inline": True},
                {"name": "💡 執行根拠", "value": notes or "CIO最終売買判定による積極エントリー", "inline": False}
            ]
        else:
            # Sell executions
            if "CIO" in rule_type or "TARGET" in rule_type:
                color = 0x3b82f6  # Blue
                title = f"🏆 【目標株価完全達成】{company_name} ({symbol}) 全株大勝利決済！"
            elif "TRAILING" in rule_type:
                color = 0x8b5cf6  # Purple
                title = f"🚀 【トレイリング天井利確】{company_name} ({symbol}) 天井付近で売り抜け！"
            elif "PARTIAL" in rule_type:
                color = 0x06b6d4  # Cyan
                title = f"🎯 【第1弾・ハーフ利確】{company_name} ({symbol}) 半分利益ロック！"
            elif "BREAKEVEN" in rule_type:
                color = 0x64748b  # Gray
                title = f"🛡️ 【建値撤退ストップ】{company_name} ({symbol}) 損失ゼロで撤退完了"
            else:
                color = 0xef4444  # Red
                title = f"🛡️ 【リスク損切り執行】{company_name} ({symbol}) リスク管理撤退"

            desc = f"ポジション管理ルールに基づき自動売却を執行しました。\n**決済内容: {quantity:,}株 @ {price:,.2f} {currency}**"
            fields = [
                {"name": "💰 確定損益", "value": f"**{pnl_amount:+,.1f} {currency} ({pnl_pct:+.1f}%)**", "inline": True},
                {"name": "⚙️ 発動ルール", "value": f"`{rule_type}`", "inline": True},
                {"name": "📝 取引メモ", "value": notes or "自動ポジション管理によるエグジット", "inline": False}
            ]

        embed = {
            "title": title,
            "description": desc,
            "color": color,
            "fields": fields,
            "footer": {
                "text": "Lumina AI Autonomous Hedge Fund • リアルタイム売買速報"
            },
            "timestamp": now_str
        }

        payload = {
            "content": f"📢 **【Lumina Hedge Fund 速報】{title}**",
            "embeds": [embed]
        }
        return cls._send_payload(payload)

    @classmethod
    def notify_discovery(cls, discovered_items: List[Dict[str, Any]]) -> bool:
        """Send notification when new catalyst stocks are auto-added to the custom watchlist"""
        if not discovered_items:
            return False

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fields = []
        for it in discovered_items[:5]:
            sym = it.get("symbol", "")
            name = it.get("name", sym)
            cat = it.get("category", "")
            thesis = it.get("thesis", "")
            fields.append({
                "name": f"⭐ {name} ({sym})",
                "value": f"**区分:** {cat}\n**好材料:** {thesis[:150]}",
                "inline": False
            })

        embed = {
            "title": f"📰 【AI速報発掘】{len(discovered_items)}銘柄をカスタム監視リストに自動登録！",
            "description": "最新の市場材料・適時開示ニュースから、本質的な企業価値向上につながる好材料を持つ銘柄を発掘しました。以降のパトロールで押し目買いを自動監視します。",
            "color": 0xf59e0b,  # Amber
            "fields": fields,
            "footer": {
                "text": "Lumina AI Autonomous Hedge Fund • 材料速報スキャナー"
            },
            "timestamp": now_str
        }

        payload = {
            "content": f"🌟 **【注目株自動発掘】{len(discovered_items)}件の新規材料株を監視リストに追加しました！**",
            "embeds": [embed]
        }
        return cls._send_payload(payload)

    @classmethod
    def notify_council_verdict(cls, council_res: Dict[str, Any]) -> bool:
        """Send council meeting verdict summary to Discord"""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sym = council_res.get("symbol", "")
        name = council_res.get("company_name", sym)
        curr = council_res.get("currency", "JPY")
        price = council_res.get("current_price", 0.0)
        verdict = council_res.get("verdict", {})
        action = verdict.get("action", "HOLD")
        action_label = verdict.get("action_label", "様子見")
        score = verdict.get("confidence_score", 50)
        t_price = verdict.get("target_price")
        s_price = verdict.get("stop_loss_price")
        thesis = verdict.get("thesis_summary", "")

        color = 0x10b981 if action in ["BUY", "ACCUMULATE"] else (0xef4444 if action in ["SELL", "REDUCE"] else 0xf59e0b)

        embed = {
            "title": f"🏛️ 【AI投資合議速報】{name} ({sym}) — {action_label} (確信度: {score}点)",
            "description": f"**現在値: {price:,.2f} {curr}**\n\nバフェット・グレアム・キャシー・リスク管理者の合議によりCIO判定が下されました。",
            "color": color,
            "fields": [
                {"name": "🎯 目標株価", "value": f"{t_price:,.2f} {curr}" if t_price else "設定なし", "inline": True},
                {"name": "🛡️ 損切り価格", "value": f"{s_price:,.2f} {curr}" if s_price else "設定なし", "inline": True},
                {"name": "💡 CIO総括・投資テーゼ", "value": thesis[:300] if thesis else "なし", "inline": False}
            ],
            "footer": {
                "text": "Lumina AI Autonomous Hedge Fund • 5-Agent Council"
            },
            "timestamp": now_str
        }

        payload = {
            "content": f"🏛️ **【合議速報】{name} ({sym}) の判定: {action_label}**",
            "embeds": [embed]
        }
        return cls._send_payload(payload)

    @classmethod
    def notify_weekly_alpha_briefing(cls, briefing: Dict[str, Any]) -> bool:
        """Send weekly alpha research briefing (Top 5 Alpha Picks) to Discord"""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        theme = briefing.get("weekly_theme", "厳選クオリティ・アルファ探索")
        regime = briefing.get("market_regime", "中立")
        outlook = briefing.get("cio_outlook", "")
        top_picks = briefing.get("top_picks", [])
        total_scanned = briefing.get("total_universe_scanned", 100)

        fields = [
            {"name": "🌊 市場レジーム", "value": str(regime), "inline": True},
            {"name": "🔭 探索ユニバース", "value": f"{total_scanned}銘柄スキャン完了", "inline": True},
            {"name": "💡 CIO週初ステートメント", "value": outlook[:250] if outlook else "なし", "inline": False}
        ]

        for p in top_picks[:5]:
            sym = p.get("symbol", "")
            name = p.get("name", sym)
            score = p.get("conviction_score", 0)
            bt = p.get("backtest", {})
            bt_str = ""
            if bt and bt.get("status") == "SUCCESS":
                bt_str = f" | 過去2年検証: 勝率 **{bt.get('win_rate_pct')}%** (PF {bt.get('profit_factor')})"
            
            upside = p.get("target_upside_pct", 0.0)
            sl = p.get("stop_loss_pct", 0.0)
            cat = p.get("catalyst", "")
            
            field_val = (
                f"確信度: **{score}点**{bt_str}\n"
                f"目標: **+{upside:.1f}%** / 損切: **{sl:.1f}%**\n"
                f"根拠: {cat[:90]}"
            )
            fields.append({
                "name": f"💎 第{p.get('rank', 1)}位: {name} ({sym})",
                "value": field_val,
                "inline": False
            })

        embed = {
            "title": f"🏛️ 【Lumina AI 週末研究室】今週の特選アルファ銘柄 Top 5",
            "description": f"**今週のメイン投資テーマ: 『{theme}』**\n週末の市場休場中に過去2年バックテスト検証を完了しました。",
            "color": 0x10b981,
            "fields": fields,
            "footer": {
                "text": "Lumina Capital v4.0 • Autonomous Alpha Research Lab"
            },
            "timestamp": now_str
        }

        payload = {
            "content": f"📢 **【週末AI研究室】今週の特選アルファ銘柄 Top 5 レポートが届きました！**",
            "embeds": [embed]
        }
        return cls._send_payload(payload)

    @classmethod
    def notify_weekly_paid_note(cls, note_info: Dict[str, Any]) -> bool:
        """Send notification when a weekly paid note draft is created"""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        title = note_info.get("title", "【来週上がる株・厳選本命】AIヘッジファンド勝負銘柄")
        url = note_info.get("url", "")
        edit_url = note_info.get("edit_url", "")
        symbol = note_info.get("symbol", "")
        name = note_info.get("company_name", symbol)
        price = note_info.get("price", 500)
        target_price = note_info.get("target_price", "N/A")
        stop_loss = note_info.get("stop_loss", "N/A")
        call_wall = note_info.get("call_wall", "N/A")
        conviction = note_info.get("conviction_score", "N/A")
        eyecatch_ok = note_info.get("eyecatch_attached", False)

        fields = [
            {"name": "🎯 本命選定銘柄", "value": f"**{name} ({symbol})**", "inline": True},
            {"name": "💰 販売設定価格", "value": f"**{price:,} 円** (有料設定)", "inline": True},
            {"name": "🔥 確信度スコア", "value": f"**{conviction} 点 / 100**", "inline": True},
            {"name": "📈 目標株価", "value": str(target_price), "inline": True},
            {"name": "🛡️ 損切り防壁 (-13.0%)", "value": str(stop_loss), "inline": True},
            {"name": "🧱 Call Wall (ガンマの壁)", "value": str(call_wall), "inline": True},
            {"name": "🎨 アイキャッチ画像", "value": "✅ 文字入り公式ヘッダー添付済" if eyecatch_ok else "⚠️ 未添付", "inline": True},
            {"name": "📝 note編集画面", "value": f"[▶️ noteエディターで確認・公開する]({edit_url})" if edit_url else "N/A", "inline": False}
        ]

        embed = {
            "title": f"💎 【週刊AIアルファ】有料note下書き保存完了！",
            "description": f"**{title}**\n\n大口需給（Call Wall）× カタリストによる来週の勝負銘柄レポートがnote.comの下書きに保存されました。",
            "color": 0x6366f1,
            "fields": fields,
            "footer": {
                "text": "Lumina Capital v5.2 • Weekly Paid Note Pipeline"
            },
            "timestamp": now_str
        }

        payload = {
            "content": f"💎 **【週刊AIアルファ】来週上がる株の有料note下書きが自動生成・保存されました！**",
            "embeds": [embed]
        }
        return cls._send_payload(payload)

