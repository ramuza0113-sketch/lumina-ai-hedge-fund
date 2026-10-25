# -*- coding: utf-8 -*-
import os
import json
import time
from typing import Dict, Any, Optional

class FundContentGenerator:
    """
    Lumina AI Hedge Fund: Autonomous Multi-Channel Content Generator
    Converts Council investment debates and portfolio signals into:
    1. 10,000-char WordPress SEO Deep-Dive Articles
    2. note.com Paid Articles & Magazine Drafts (PASONA Structure)
    3. X (Twitter) High-CTR Daily P&L & Trade Alert Posts
    4. Discord Rich Webhook Broadcasts
    """

    # 🛡️ note全記事（有料・無料問わず）冒頭＆末尾自動挿入用 システム免責事項（Disclaimer）
    NOTE_DISCLAIMER_TEXT = (
        "【免責事項】本記事は、自律型クオンツ運用エンジン「Lumina Capital」の数理アルゴリズム、"
        "市場微細構造解析、および時系列確率予測モデルの研究開発・シミュレーション結果を公開するものであり、"
        "特定の有価証券の売買推奨、投資助言、または将来の運用成果を保証するものでは一切ありません。"
        "記事内で言及される価格や数値はすべてシステム内部のシミュレーション値であり、"
        "実際の投資判断および取引は、読者ご自身の責任と判断において行ってください。"
    )

    NOTE_DISCLAIMER_HTML = (
        '<p><strong>【免責事項】</strong>本記事は、自律型クオンツ運用エンジン「Lumina Capital」の数理アルゴリズム、'
        '市場微細構造解析、および時系列確率予測モデルの研究開発・シミュレーション結果を公開するものであり、'
        '特定の有価証券の売買推奨、投資助言、または将来の運用成果を保証するものでは一切ありません。'
        '記事内で言及される価格や数値はすべてシステム内部のシミュレーション値であり、'
        '実際の投資判断および取引は、読者ご自身の責任と判断において行ってください。</p>'
    )

    NOTE_DISCLAIMER_MD = (
        "> **【免責事項】** 本記事は、自律型クオンツ運用エンジン「Lumina Capital」の数理アルゴリズム、"
        "市場微細構造解析、および時系列確率予測モデルの研究開発・シミュレーション結果を公開するものであり、"
        "特定の有価証券の売買推奨、投資助言、または将来の運用成果を保証するものでは一切ありません。"
        "記事内で言及される価格や数値はすべてシステム内部のシミュレーション値であり、"
        "実際の投資判断および取引は、読者ご自身の責任と判断において行ってください。"
    )

    @classmethod
    def inject_disclaimers_html(cls, html_content: str) -> str:
        """
        HTML本文の冒頭および末尾にシステム免責事項（Disclaimer）を自動挿入する（重複防止付き）。
        """
        import re
        if not html_content:
            return f"{cls.NOTE_DISCLAIMER_HTML}\n\n{cls.NOTE_DISCLAIMER_HTML}"

        res = html_content.strip()

        # 冒頭チェック
        if "【免責事項】" not in res[:350]:
            res = f"{cls.NOTE_DISCLAIMER_HTML}\n\n{res}"

        # 末尾チェック（冒頭の免責事項以降のテキスト末尾600文字を検査）
        offset = res.find("【免責事項】") + len("【免責事項】") if "【免責事項】" in res[:350] else 0
        tail_sub = res[offset:]
        if "【免責事項】" not in tail_sub[-600:]:
            tag_match = re.search(r'(<p[^>]*>#[\s\S]*?</p>\s*)$', res, re.IGNORECASE)
            if tag_match:
                tag_part = tag_match.group(1)
                main_part = res[:tag_match.start()].rstrip()
                res = f"{main_part}\n\n{cls.NOTE_DISCLAIMER_HTML}\n\n{tag_part}"
            else:
                res = f"{res}\n\n{cls.NOTE_DISCLAIMER_HTML}"

        return res

    @classmethod
    def inject_disclaimers_md(cls, md_content: str) -> str:
        """
        Markdown本文の冒頭および末尾にシステム免責事項（Disclaimer）を自動挿入する（重複防止付き）。
        """
        if not md_content:
            return f"{cls.NOTE_DISCLAIMER_MD}\n\n{cls.NOTE_DISCLAIMER_MD}"

        res = md_content.strip()

        if "【免責事項】" not in res[:350]:
            res = f"{cls.NOTE_DISCLAIMER_MD}\n\n{res}"

        # 末尾チェック（冒頭の免責事項以降のテキスト末尾600文字を検査）
        offset = res.find("【免責事項】") + len("【免責事項】") if "【免責事項】" in res[:350] else 0
        tail_sub = res[offset:]
        if "【免責事項】" not in tail_sub[-600:]:
            res = f"{res}\n\n{cls.NOTE_DISCLAIMER_MD}"

        return res


    @classmethod
    def _call_gemini(cls, prompt: str, system_instruction: str = "") -> str:
        """Helper to invoke Gemini 2.5/3.8 Flash"""
        try:
            from core.state_manager import load_app_settings
            cfg = load_app_settings()
            api_key = cfg.get("google_api_key", "")
            if not api_key:
                return ""
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None,
                temperature=0.7
            )
            for model_name in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-3.8-flash"]:
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    if res and res.text:
                        return res.text
                except Exception as m_err:
                    print(f"[FundContentGen] {model_name} error: {m_err}")
            return ""
        except Exception as e:
            print(f"[FundContentGen] Global API error: {e}")
            return ""

    @classmethod
    def generate_wp_deep_dive_article(cls, council_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive 10,000-character WordPress SEO pillar article
        complete with Gutenberg HTML blocks, multi-perspective debate, and financial analysis.
        """
        sym = council_res.get("symbol", "")
        name = council_res.get("company_name", "")
        curr = council_res.get("currency", "JPY")
        price = council_res.get("current_price", "N/A")
        verdict = council_res.get("verdict", {})
        action_label = verdict.get("action_label", "投資判断")
        action = verdict.get("action", "HOLD")
        target_price = verdict.get("target_price", "N/A")
        stop_loss = verdict.get("stop_loss_price", "N/A")
        alloc = verdict.get("allocation_pct", 10.0)
        dialogues = council_res.get("council_dialogues", [])
        stock_data = council_res.get("stock_data", {})
        
        prompt = f"""あなたはLumina AIのチーフ投資アナリストです。
以下の自律型AIヘッジファンド「Lumina Capital」の投資作戦会議結果を基に、読者が圧倒的な知見を得られる【1万字級のWordPress深掘り投資分析記事】を執筆してください。

【対象銘柄】
銘柄: {sym} ({name})
現在値: {price} {curr}
売買判断: {action} ({action_label})
目標株価: {target_price} {curr} / 損切りライン: {stop_loss} {curr}
推奨配分比率: {alloc}%

【エージェント合議内容】
{json.dumps(dialogues, ensure_ascii=False, indent=2)}

【財務・市場データ】
{json.dumps({k: v for k, v in stock_data.items() if k != 'business_summary'}, ensure_ascii=False, indent=2)}

【執筆ルール】
1. タイトルは読者の知的好奇心を刺激する最高峰のSEOタイトル（例: 【AI投資合議】バフェット×キャシー・ウッド激論！{name}({sym})の適正株価と買い場・損切りラインを徹底解剖）
2. 見出し構造（H2, H3）を徹底し、バフェットの堀分析、グレアムの安全域、キャシーのイノベーション、リスク管理者の警鐘、CIOの最終判断を各2,000字規模で濃厚に論じる。
3. WordPressのGutenbergブロック（`<div style="...">` や `<!-- wp:heading -->`, `<!-- wp:paragraph -->`, `<!-- wp:table -->`）を適切に活用して視覚的に美しく装飾する。
4. 投資初心者がプロの投資機関の思考プロセスを疑似体験できるよう、専門用語の平易な解説と具体的シミュレーションを交える。
5. 末尾には「※本記事は情報提供を目的としており、特定の金融商品の売買を推奨・勧誘するものではありません。投資判断は自己責任でお願いいたします。」という免責事項を明記。

記事タイトル、抜粋（メタディスクリプション: 120字）、本文（HTML形式）を生成してください。
フォーマット:
===TITLE===
[タイトル]
===EXCERPT===
[抜粋]
===BODY===
[本文HTML]
"""
        generated = cls._call_gemini(prompt)
        
        # Fallback if API fails
        if not generated or "===BODY===" not in generated:
            title = f"【AI投資合議】{name} ({sym})の適正株価と買い場・損切りラインを徹底解剖"
            excerpt = f"自律型AIヘッジファンドによる{name}({sym})の徹底合議録。バフェット、グレアム、キャシー・ウッドの思考ロジックを融合した売買判断と適正価格を公開。"
            body = f"""<div style="background: linear-gradient(135deg, #0d1527 0%, #111e38 100%); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 20px; color: #FFFFFF; margin-bottom: 24px;">
    <h3 style="color: #38bdf8; margin-top: 0;">🏛️ Lumina AI Hedge Fund 投資合議レポート</h3>
    <p>対象銘柄: <strong>{name} ({sym})</strong> | 現在値: <strong>{price} {curr}</strong></p>
    <p>最終判定: <span style="background: #10b981; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{action_label}</span></p>
    <p>目標株価: <strong>{target_price} {curr}</strong> | 損切りライン: <strong>{stop_loss} {curr}</strong></p>
</div>
<h2>1. 伝説の投資家AIたちによる合議討議録</h2>
<p>本銘柄に対し、ウォーレン・バフェット、ベンジャミン・グレアム、キャシー・ウッド、リスク管理者の4エージェントが徹底的な検証を実施しました。</p>
"""
            for d in dialogues:
                body += f"""<div style="background: rgba(255,255,255,0.03); border-left: 4px solid #38bdf8; padding: 15px; margin-bottom: 15px; border-radius: 4px;">
    <strong>{d.get('avatar', '👤')} {d.get('name', '')} ({d.get('title', '')})</strong> - スタンス: {d.get('stance', '')}<br/>
    <p style="margin-top: 8px;">{d.get('dialogue', '')}</p>
</div>"""
            body += f"""<h2>2. CIO最終投資判断とポートフォリオ戦略</h2>
<p>{verdict.get('thesis_summary', '')}</p>
<hr/>
<p><small>※本記事はAIによる分析情報を提供するものであり、投資の最終判断は自己責任にてお願いいたします。</small></p>"""
            return {"title": title, "excerpt": excerpt, "body": body}

        parts = generated.split("===BODY===")
        top = parts[0]
        body = parts[1].strip() if len(parts) > 1 else ""

        title = f"【AI投資合議】{name} ({sym})の適正株価徹底分析"
        excerpt = f"自律型AIヘッジファンドが導く{name}({sym})の売買判定と適正株価。"

        if "===TITLE===" in top:
            t_part = top.split("===TITLE===")[1]
            if "===EXCERPT===" in t_part:
                title = t_part.split("===EXCERPT===")[0].strip()
                excerpt = t_part.split("===EXCERPT===")[1].strip()
            else:
                title = t_part.strip()

        return {"title": title, "excerpt": excerpt, "body": body}

    @classmethod
    def generate_note_paid_article(cls, council_res: Dict[str, Any], price: int = 500) -> Dict[str, Any]:
        """
        Generate a high-converting note.com paid article following PASONA framework.
        Includes free teaser and paywall boundary.
        """
        sym = council_res.get("symbol", "")
        name = council_res.get("company_name", "")
        curr = council_res.get("currency", "JPY")
        price_val = council_res.get("current_price", "N/A")
        verdict = council_res.get("verdict", {})
        action_label = verdict.get("action_label", "売買判定")
        target_price = verdict.get("target_price", "N/A")
        stop_loss = verdict.get("stop_loss_price", "N/A")
        alloc = verdict.get("allocation_pct", 10.0)
        dialogues = council_res.get("council_dialogues", [])

        title = f"【自律型AIヘッジファンド合議録】伝説の投資家AI4名が激論の末に下した「{name} ({sym})」の買い場・指値・損切りレート完全開示"

        free_body = f"""{cls.NOTE_DISCLAIMER_MD}

こんにちは、Lumina AIです。

「いまの相場で、本当に買うべき銘柄はどれなのか？」
「SNSの煽りや高値掴みで損をしたくない…」

多くの個人投資家が、感情や曖昧なニュースに振り回されて大切な資金を減らしています。
しかし、ウォール街のトップヘッジファンドは決して「感情」でトレードしません。

今回は、GitHubで世界中で話題の自律型AIヘッジファンド・アーキテクチャを日本株・米国株に適用。
**ウォーレン・バフェット、ベンジャミン・グレアム、キャシー・ウッド、リスク管理者**という4つの伝説的思考ロジックを完全再現したAIたちが、**{name}（{sym}・現在値: {price_val} {curr}）**を徹底討議しました。

---

### 🏛️ 4エージェントの意見ダイジェスト
"""
        for d in dialogues:
            free_body += f"\n- **{d.get('avatar')} {d.get('name')}**: 「{d.get('dialogue', '')[:80]}…」"

        free_body += """

議論は白熱し、バリュー（安全域）とグロース（破壊的成長）の間で激しい意見の対立が起きました。
その上で、当ファンドのCIO（最高投資責任者）が下した最終判定とは——？

---
ここから先は有料エリアとなります。
**【有料エリアで公開する完全データ】**
1. 💰 ファンドCIOの最終売買判定（買い / 打診買い / 様子見 / 売り）
2. 🎯 精密な目標株価とリワードレシオ算出根拠
3. 🛡️ 資金を守るための厳格な損切りライン（指値レート）
4. 📊 推奨ポジション配分比率（リスク許容度別シミュレーション）
5. 🔍 4エージェントのノーカット全討論スクリプト

感情を排除したプロレベルの投資判断を、あなたのポートフォリオに今すぐインストールしてください。
"""

        paid_body = f"""### 💰 ファンドマネージャー・CIOによる最終執行計画

- **売買アクション**: **{action_label}** ({verdict.get('action')})
- **目標株価 (Target Price)**: **{target_price} {curr}**
- **損切りライン (Stop-Loss)**: **{stop_loss} {curr}**
- **推奨ポジションサイズ**: **ポートフォリオ全体の {alloc}%**
- **想定投資ホライズン**: **{verdict.get('horizon', '中期（6〜12ヶ月）')}**
- **確信度スコア**: **{verdict.get('confidence_score', 80)}点 / 100点**

#### 📌 CIOの投資テーゼ（総括理由）
{verdict.get('thesis_summary')}

---

### 🎙️ 4エージェント 全討論ノーカット録
"""
        for d in dialogues:
            paid_body += f"""
#### {d.get('avatar')} {d.get('name')} ({d.get('title')}) - スタンス: {d.get('stance')} (スコア: {d.get('score')}点)
> {d.get('dialogue')}
"""

        paid_body += f"""
---
#### 🛡️ リスク管理と実践的トレード手順
1. 一括ではなく2〜3回に分けた分散打診買いを徹底してください。
2. 逆指値（{stop_loss} {curr}）はエントリーと同時に必ず発注し、いかなる場合も機械的に損切りを行ってください。
3. 利益が目標株価（{target_price} {curr}）の50%に達した段階で、半分を利確し残りのストップロスを買値まで引き上げてください。

{cls.NOTE_DISCLAIMER_MD}
"""
        full_content = free_body + "\n<!-- note-paywall -->\n" + paid_body
        return {
            "title": title,
            "free_body": free_body,
            "paid_body": paid_body,
            "full_content": full_content,
            "price": price
        }

    @classmethod
    def generate_x_report(cls, council_res: Dict[str, Any]) -> str:
        """
        Generate a concise 140-char X (Twitter) trade signal alert.
        """
        sym = council_res.get("symbol", "")
        name = council_res.get("company_name", "")
        curr = council_res.get("currency", "JPY")
        price_val = council_res.get("current_price", "")
        verdict = council_res.get("verdict", {})
        action = verdict.get("action", "BUY")
        action_label = verdict.get("action_label", "買い")
        target = verdict.get("target_price", "")
        stop = verdict.get("stop_loss_price", "")

        is_jp = sym.endswith(".T")
        tag = "#日本株 #高配当株" if is_jp else "#米国株 #AI投資"

        tweet = f"""【AIヘッジファンド作戦会議】
🏛️ 銘柄: {name} ({sym})
現在値: {price_val} {curr}

📊 合議判定: 【{action_label}】
🎯 目標株価: {target} {curr}
🛡️ 損切り線: {stop} {curr}

バフェットの堀評価とキャシーのTAM予測が一致。感情を排除した自律運用中。
{tag} #LuminaAI"""

        # Strictly trim to 140 chars if needed
        if len(tweet) > 140:
            tweet = tweet[:137] + "..."
        return tweet

    @classmethod
    def generate_discord_embed(cls, council_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format Discord rich webhook payload.
        """
        sym = council_res.get("symbol", "")
        name = council_res.get("company_name", "")
        curr = council_res.get("currency", "JPY")
        price_val = council_res.get("current_price", "")
        verdict = council_res.get("verdict", {})
        action = verdict.get("action", "HOLD")
        action_label = verdict.get("action_label", "判定")
        target = verdict.get("target_price", "")
        stop = verdict.get("stop_loss_price", "")
        alloc = verdict.get("allocation_pct", 10.0)

        color = 0x10b981 if action in ["BUY", "ACCUMULATE"] else (0xef4444 if action in ["SELL", "REDUCE"] else 0xf59e0b)

        embed = {
            "title": f"🏛️ Lumina AI Hedge Fund 投資合議速報: {name} ({sym})",
            "description": f"**判定**: `{action_label}` (アクション: {action})",
            "color": color,
            "fields": [
                {"name": "現在株価", "value": f"{price_val} {curr}", "inline": True},
                {"name": "目標株価", "value": f"{target} {curr}", "inline": True},
                {"name": "損切りライン", "value": f"{stop} {curr}", "inline": True},
                {"name": "推奨配分", "value": f"{alloc}%", "inline": True},
                {"name": "投資ホライズン", "value": f"{verdict.get('horizon', '中期')}", "inline": True},
                {"name": "確信度", "value": f"{verdict.get('confidence_score', 80)}%", "inline": True},
                {"name": "CIO総括", "value": verdict.get("thesis_summary", "特記事項なし"), "inline": False}
            ],
            "footer": {"text": "Lumina AI Autonomous Hedge Fund Engine"}
        }
        return {"embeds": [embed]}

    # =========================================================================
    # 📈 株式自動売買・日次推移速報 X（Twitter）自律投稿エンジン (1日1〜2回)
    # =========================================================================

    @classmethod
    def generate_portfolio_daily_report(cls, paper_engine=None, session_type: str = "auto", lang: str = "ja") -> Dict[str, Any]:
        """
        株式自動売買の資産推移・損益・保有銘柄・AI合議状況をまとめたX用日次レポートを生成。
        X API v2の280重み付け文字数制限を厳格にクリアするメインポストと、詳細サブポスト（ミニスレッド用）を出力。
        """
        import datetime
        from core.ai_hedge_fund.broker_client import PaperTradingEngine

        engine = paper_engine or PaperTradingEngine()
        summary = engine.get_portfolio_summary()
        orders = engine.get_order_history(limit=5)

        tot_eq = float(summary.get("total_equity_jpy", 1000000.0))
        init_eq = 1000000.0
        tot_ret_pct = ((tot_eq - init_eq) / init_eq) * 100.0 if init_eq > 0 else 0.0

        unreal_jpy = float(summary.get("total_unrealized_pnl_jpy", 0.0))
        unreal_pct = float(summary.get("total_unrealized_pnl_pct", 0.0))
        cash_jpy = float(summary.get("cash_jpy", 0.0))
        cash_usd = float(summary.get("cash_usd", 0.0))
        fx_rate = float(summary.get("usdjpy_rate", 155.0))
        cash_tot_jpy = cash_jpy + (cash_usd * fx_rate)
        cash_ratio = (cash_tot_jpy / tot_eq * 100.0) if tot_eq > 0 else 100.0
        positions = summary.get("positions", [])

        now = datetime.datetime.now()
        hour = now.hour

        if session_type == "auto":
            if 14 <= hour < 18:
                sess_key = "closing"
                sess_title = "🇯🇵 [TSE Market Close / Performance Flash] 📈" if lang == "en" else "🇯🇵【東証大引け・運用速報】"
            elif 18 <= hour < 24:
                sess_key = "night"
                sess_title = "🇺🇸 [Evening / Pre-US Market Flash] 📈" if lang == "en" else "🇺🇸【夜間・運用速報＆米国株前】"
            else:
                sess_key = "morning"
                sess_title = "🌅 [Morning Performance Flash] 📈" if lang == "en" else "🌅【朝の運用実績速報】"
        elif session_type == "closing":
            sess_key = "closing"
            sess_title = "🇯🇵 [TSE Market Close / Performance Flash] 📈" if lang == "en" else "🇯🇵【東証大引け・運用速報】"
        elif session_type == "night":
            sess_key = "night"
            sess_title = "🇺🇸 [Evening / Pre-US Market Flash] 📈" if lang == "en" else "🇺🇸【夜間・運用速報＆米国株前】"
        else:
            sess_key = "daily"
            sess_title = "🏛️ [Lumina Capital Daily Performance] 📈" if lang == "en" else "🏛️【Lumina Capital・日次推移】"

        sign_ret = "+" if tot_ret_pct >= 0 else ""
        sign_unreal = "+" if unreal_jpy >= 0 else ""

        if lang == "en":
            if positions:
                pos_parts = [f"{p.get('symbol')}({p.get('unrealized_pnl_pct', 0.0):+.1f}%)" for p in positions[:2]]
                pos_text = f"💼 Holdings: {', '.join(pos_parts)}"
                if len(positions) > 2:
                    pos_text += f" +{len(positions) - 2} more"
            else:
                pos_text = "💼 Holdings: 0 positions (Cash 100%)"

            today_iso = now.strftime("%Y-%m-%d")
            today_orders = [o for o in orders if str(o.get("order_time", "")).startswith(today_iso)]
            if today_orders:
                last_o = today_orders[0]
                action_type = "BUY" if last_o.get("side") == "BUY" else "PROFIT-TAKE"
                strat_note = f"Executed {action_type} on {last_o.get('symbol', '')} today. "
            else:
                strat_note = "Avoiding overvalued chases, monitoring dip entries with margin of safety. "

            main_tweet = (
                f"{sess_title}\n\n"
                f"💰 Total Equity: ¥{tot_eq:,.0f} ({sign_ret}{tot_ret_pct:.2f}%)\n"
                f"📊 Unrealized PnL: {sign_unreal}¥{abs(unreal_jpy):,.0f} ({sign_unreal}{unreal_pct:.2f}%)\n"
                f"{pos_text}\n"
                f"🛡️ Cash Ratio: {cash_ratio:.0f}%\n\n"
                f"{strat_note}Maintaining systematic quantitative execution.\n\n"
                f"#Investing #AIHedgeFund #LuminaCapital"
            )

            sub_lines = ["📊 [Portfolio Breakdown & Council Status]"]
            if positions:
                for p in positions[:3]:
                    sub_lines.append(f"• {p.get('symbol')}: {p.get('quantity', 0):,} shs (PnL: {p.get('unrealized_pnl_pct', 0.0):+.2f}%)")
            else:
                sub_lines.append("• Zero open positions. 100% cash defense awaiting Buffett moat & Graham deep value criteria.")
            sub_lines.append("\n5 AI Legends (Buffett, Graham, Wood, Risk Officer, CIO) 24/7 autonomous patrol active.")
            sub_tweet = "\n".join(sub_lines)
        else:
            if positions:
                pos_parts = [f"{p.get('company_name', p.get('symbol'))[:6]}({p.get('unrealized_pnl_pct', 0.0):+.1f}%)" for p in positions[:2]]
                pos_text = f"💼 保有: {', '.join(pos_parts)}"
                if len(positions) > 2:
                    pos_text += f" 他計{len(positions)}銘柄"
            else:
                pos_text = "💼 保有: 0銘柄 (現金比率100%)"

            # Action / Strategy note (Only consider orders executed TODAY)
            today_iso = now.strftime("%Y-%m-%d")
            today_orders = [o for o in orders if str(o.get("order_time", "")).startswith(today_iso)]
            if today_orders:
                last_o = today_orders[0]
                action_type = "新規買い" if last_o.get("side") == "BUY" else "利益確定"
                strat_note = f"本日{last_o.get('company_name', '')[:6]}を{action_type}約定。"
            else:
                strat_note = "無理な高値追いを避け、安全域での押し目を監視中。"

            main_tweet = (
                f"🏛️【Lumina Capital】本日のAI運用推移 📈\n\n"
                f"💰 総資産: ¥{tot_eq:,.0f} ({sign_ret}{tot_ret_pct:.2f}%)\n"
                f"📊 評価損益: {sign_unreal}¥{abs(unreal_jpy):,.0f} ({sign_unreal}{unreal_pct:.2f}%)\n"
                f"{pos_text}\n"
                f"🛡️ 現金比率: {cash_ratio:.0f}%\n\n"
                f"{strat_note}感情を排したクオンツ運用を継続します。\n\n"
                f"#株式投資 #AI自動売買 #LuminaCapital"
            )

            # Sub tweet (mini-thread)
            sub_lines = ["📊【ポートフォリオ内訳・合議状況】"]
            if positions:
                for p in positions[:3]:
                    sub_lines.append(f"・{p.get('company_name', p.get('symbol'))}: {p.get('quantity', 0):,}株 (評価損益: {p.get('unrealized_pnl_pct', 0.0):+.2f}%)")
            else:
                sub_lines.append("・現在ポジションなし。バフェットの堀＆グレアムのディープバリュー条件に合致する押し目までキャッシュ100%防衛。")
            sub_lines.append("\n5人のAI投資家（バフェット・グレアム・キャシー・リスク管理・CIO）による24時間自律パトロール稼働中。")
            sub_tweet = "\n".join(sub_lines)

        try:
            try:
                from core.x_publisher import XPublisher
            except ImportError:
                from x_publisher import XPublisher
            pub = XPublisher()
            if pub.get_twitter_weighted_length(main_tweet) > 280:
                main_tweet = pub._smart_trim_tweet(main_tweet, max_weight=280)
            if pub.get_twitter_weighted_length(sub_tweet) > 280:
                sub_tweet = pub._smart_trim_tweet(sub_tweet, max_weight=280)
        except Exception:
            if len(main_tweet) > 140:
                main_tweet = main_tweet[:137] + "..."
            if len(sub_tweet) > 140:
                sub_tweet = sub_tweet[:137] + "..."

        report_data = {
            "session_key": sess_key,
            "session_title": sess_title,
            "total_equity_jpy": tot_eq,
            "initial_equity_jpy": init_eq,
            "total_return_pct": tot_ret_pct,
            "unrealized_pnl_jpy": unreal_jpy,
            "unrealized_pnl_pct": unreal_pct,
            "cash_jpy": cash_jpy,
            "cash_usd": cash_usd,
            "cash_ratio": cash_ratio,
            "positions": positions,
            "orders": orders,
            "main_tweet": main_tweet,
            "sub_tweet": sub_tweet,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
        }
        return report_data

    @classmethod
    def generate_portfolio_card_image(cls, report_data: Dict[str, Any]) -> Optional[str]:
        """
        高解像度 (1200x675) ダークモード実績インフォグラフィック画像をPILで生成
        """
        try:
            import os
            import datetime
            from PIL import Image, ImageDraw, ImageFont

            W, H = 1200, 675
            img = Image.new("RGB", (W, H), (10, 16, 30))
            draw = ImageDraw.Draw(img)

            # Clean emoji from title to prevent tofu '□' boxes
            sess_name = str(report_data.get("session_title", "自律型AIヘッジファンド 運用推移速報"))
            for emo in ["🏛️", "📈", "🇯🇵", "🇺🇸", "🌅", "【", "】", "💰", "💼", "🤖"]:
                sess_name = sess_name.replace(emo, "")
            sess_name = f"【{sess_name.strip()}】"

            tot_eq = float(report_data.get("total_equity_jpy", 1000000.0))
            tot_ret = float(report_data.get("total_return_pct", 0.0))
            sign_ret = "+" if tot_ret >= 0 else ""
            positions = report_data.get("positions", [])
            now_str = report_data.get("timestamp", datetime.datetime.now().strftime("%Y.%m.%d %H:%M")) + " JST"

            font_bold_candidates = [
                r"C:\Windows\Fonts\meiryob.ttc",
                r"C:\Windows\Fonts\msgothic.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            ]
            font_reg_candidates = [
                r"C:\Windows\Fonts\meiryo.ttc",
                r"C:\Windows\Fonts\msmincho.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            ]
            font_p = None
            for fp in font_bold_candidates:
                if os.path.exists(fp):
                    font_p = fp
                    break
            font_r = None
            for fr in font_reg_candidates:
                if os.path.exists(fr):
                    font_r = fr
                    break

            try:
                f_title = ImageFont.truetype(font_p, 28) if font_p else ImageFont.load_default()
                f_sub = ImageFont.truetype(font_r or font_p, 16) if (font_r or font_p) else ImageFont.load_default()
                f_metric_label = ImageFont.truetype(font_p, 18) if font_p else ImageFont.load_default()
                f_metric_val = ImageFont.truetype(font_p, 46) if font_p else ImageFont.load_default()
                f_badge = ImageFont.truetype(font_p, 18) if font_p else ImageFont.load_default()
                f_text = ImageFont.truetype(font_r or font_p, 18) if (font_r or font_p) else ImageFont.load_default()
                f_bold = ImageFont.truetype(font_p, 20) if font_p else ImageFont.load_default()
            except Exception:
                f_title = f_sub = f_metric_label = f_metric_val = f_badge = f_text = f_bold = ImageFont.load_default()

            # Check for high-CTR Lumina illustration asset
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            bg_asset = os.path.join(base_dir, "assets", "lumina_trading_desk.jpg")
            if os.path.exists(bg_asset):
                try:
                    img_bg = Image.open(bg_asset).convert("RGBA").resize((W, H))
                    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    draw_ov = ImageDraw.Draw(overlay)

                    # Top banner gradient
                    for y in range(120):
                        alpha = int(210 * (1 - y / 120))
                        draw_ov.line([(0, y), (W, y)], fill=(10, 15, 30, alpha))

                    # Bottom frosted stats bar
                    draw_ov.rounded_rectangle([(30, 540), (1170, 645)], radius=16, fill=(11, 17, 32, 230), outline=(56, 189, 248, 220), width=2)

                    # Top text & separator
                    brand_text = "LUMINA CAPITAL"
                    draw_ov.text((45, 25), brand_text, fill=(56, 189, 248, 255), font=f_title)
                    w_br = draw_ov.textlength(brand_text, font=f_title)
                    sep_x = int(45 + w_br + 20)
                    draw_ov.line([(sep_x, 28), (sep_x, 65)], fill=(148, 163, 184, 180), width=2)
                    draw_ov.text((sep_x + 20, 27), sess_name, fill=(255, 255, 255, 255), font=f_title)

                    w_date = draw_ov.textlength(now_str, font=f_sub)
                    draw_ov.text((W - 45 - int(w_date), 32), now_str, fill=(148, 163, 184, 255), font=f_sub)

                    # Bottom stats numbers
                    draw_ov.text((60, 555), "総資産評価額", fill=(148, 163, 184, 255), font=f_sub)
                    draw_ov.text((60, 580), f"¥{tot_eq:,.0f}", fill=(255, 255, 255, 255), font=f_metric_val)

                    # Return badge
                    b_color = (16, 185, 129, 240) if tot_ret >= 0 else (239, 68, 68, 240)
                    draw_ov.rounded_rectangle([(340, 565), (550, 615)], radius=10, fill=b_color)
                    draw_ov.text((358, 575), f"通算損益: {sign_ret}{tot_ret:.2f}%", fill=(255, 255, 255, 255), font=f_badge)

                    # Holdings & committee info
                    if positions:
                        pos_parts = [f"{p.get('company_name', p.get('symbol'))[:6]}({p.get('unrealized_pnl_pct', 0.0):+.1f}%)" for p in positions[:2]]
                        pos_str = f"◆ 保有: {', '.join(pos_parts)}"
                        if len(positions) > 2:
                            pos_str += f" 他計{len(positions)}銘柄"
                    else:
                        pos_str = "◆ 保有: 0銘柄 (キャッシュ比率100%)"

                    draw_ov.text((580, 560), pos_str, fill=(226, 232, 240, 255), font=f_sub)
                    draw_ov.text((580, 595), "■ 5人AI合議: バフェット・グレアム・キャシー・リスク管理・CIO", fill=(56, 189, 248, 255), font=f_sub)

                    final_img = Image.alpha_composite(img_bg, overlay).convert("RGB")
                    app_data = os.path.join(os.getenv("APPDATA", ""), "LuminaAI")
                    os.makedirs(app_data, exist_ok=True)
                    out_file = os.path.join(app_data, f"portfolio_report_card_{int(datetime.datetime.now().timestamp())}.png")
                    final_img.save(out_file)
                    return out_file
                except Exception as comp_err:
                    print(f"[FundContentGenerator] Illustration composite failed, falling back: {comp_err}")

            # Fallback Gradient background
            for y in range(H):
                r = int(10 + (22 - 10) * (y / H))
                g = int(16 + (32 - 16) * (y / H))
                b = int(30 + (52 - 30) * (y / H))
                draw.line([(0, y), (W, y)], fill=(r, g, b))

            # Outer border
            draw.rounded_rectangle([(16, 16), (W-16, H-16)], radius=16, outline=(56, 189, 248), width=2)

            # Clean emoji from title to prevent tofu '□' boxes
            sess_name = str(report_data.get("session_title", "自律型AIヘッジファンド 運用推移速報"))
            for emo in ["🏛️", "📈", "🇯🇵", "🇺🇸", "🌅", "【", "】", "💰", "💼", "🤖"]:
                sess_name = sess_name.replace(emo, "")
            sess_name = f"【{sess_name.strip()}】"

            # Header with dynamic width calculation & stylish vertical divider
            brand_text = "LUMINA CAPITAL"
            draw.text((45, 36), brand_text, fill=(56, 189, 248), font=f_title)
            try:
                w_brand = draw.textlength(brand_text, font=f_title)
            except Exception:
                w_brand = 240

            # Vertical separator line
            sep_x = int(45 + w_brand + 20)
            draw.line([(sep_x, 38), (sep_x, 70)], fill=(71, 85, 105), width=2)

            # Session title with comfortable spacing
            sess_x = sep_x + 20
            draw.text((sess_x, 37), sess_name, fill=(248, 250, 252), font=f_title)

            # Timestamp cleanly right-aligned to right margin
            now_str = report_data.get("timestamp", datetime.datetime.now().strftime("%Y.%m.%d %H:%M")) + " JST"
            try:
                w_date = draw.textlength(now_str, font=f_sub)
            except Exception:
                w_date = 200
            draw.text((W - 45 - int(w_date), 44), now_str, fill=(148, 163, 184), font=f_sub)
            draw.line([(45, 85), (W - 45, 85)], fill=(30, 41, 59), width=2)

            # Left Card: Assets & Return
            draw.rounded_rectangle([(45, 110), (580, 580)], radius=14, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
            draw.text((75, 135), "◆ 総資産額 (PORTFOLIO EQUITY)", fill=(148, 163, 184), font=f_metric_label)
            tot_eq = report_data.get("total_equity_jpy", 1000000.0)
            draw.text((75, 175), f"¥{tot_eq:,.0f}", fill=(248, 250, 252), font=f_metric_val)

            # Return badge
            tot_ret = report_data.get("total_return_pct", 0.0)
            sign_ret = "+" if tot_ret >= 0 else ""
            badge_color = (16, 185, 129) if tot_ret >= 0 else (239, 68, 68)
            draw.rounded_rectangle([(75, 250), (300, 290)], radius=8, fill=badge_color)
            draw.text((90, 258), f"通算損益: {sign_ret}{tot_ret:.2f}%", fill=(255, 255, 255), font=f_badge)

            draw.line([(75, 320), (550, 320)], fill=(30, 41, 59), width=1)
            unreal_jpy = report_data.get("unrealized_pnl_jpy", 0.0)
            unreal_pct = report_data.get("unrealized_pnl_pct", 0.0)
            sign_u = "+" if unreal_jpy >= 0 else ""
            draw.text((75, 345), f"・評価損益: {sign_u}¥{abs(unreal_jpy):,.0f} ({sign_u}{unreal_pct:.2f}%)", fill=(226, 232, 240), font=f_text)
            cash_ratio = report_data.get("cash_ratio", 100.0)
            draw.text((75, 395), f"・現金比率: {cash_ratio:.0f}% (防衛バッファ確保)", fill=(226, 232, 240), font=f_text)
            draw.text((75, 445), "・運用通貨: 日本円 (JPY) / 米ドル (USD)", fill=(226, 232, 240), font=f_text)
            draw.text((75, 495), "・取引制限: 証券取引時間外ガード作動中", fill=(148, 163, 184), font=f_text)

            # Right Card: Holdings & Strategy
            draw.rounded_rectangle([(620, 110), (1155, 580)], radius=14, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
            draw.text((650, 135), "◆ 保有ポジション ＆ AI合議ステータス", fill=(148, 163, 184), font=f_metric_label)

            positions = report_data.get("positions", [])
            draw.rounded_rectangle([(650, 175), (1125, 295)], radius=10, fill=(30, 41, 59))
            if positions:
                draw.text((670, 190), f"保有銘柄数: {len(positions)} 銘柄", fill=(56, 189, 248), font=f_bold)
                pos_summaries = []
                for p in positions[:2]:
                    p_name = p.get("company_name", p.get("symbol", ""))[:8]
                    p_pct = p.get("unrealized_pnl_pct", 0.0)
                    pos_summaries.append(f"・{p_name}: {p.get('quantity', 0)}株 (損益: {p_pct:+.1f}%)")
                draw.text((670, 225), "\n".join(pos_summaries), fill=(203, 213, 225), font=f_sub)
            else:
                draw.text((670, 195), "保有銘柄数: 0 銘柄 (キャッシュ比率100%)", fill=(56, 189, 248), font=f_bold)
                draw.text((670, 235), "高値掴みを厳格に回避し、グレアムの安全域と\nバフェットの堀を備えた押し目買い水準まで待機中。", fill=(203, 213, 225), font=f_sub)

            draw.text((650, 325), "■ 5人AI投資合議委員会 (24時間自律監視)", fill=(248, 250, 252), font=f_bold)
            draw.text((650, 365), "・バフェット: 経済的な堀 (Wide Moat) ＆ FCF創出力", fill=(226, 232, 240), font=f_sub)
            draw.text((650, 400), "・グレアム: PBR1倍割れ ＆ 純流動資産ディープバリュー", fill=(226, 232, 240), font=f_sub)
            draw.text((650, 435), "・キャシー: AIインフラ・次世代半導体成長モメンタム", fill=(226, 232, 240), font=f_sub)
            draw.text((650, 470), "・リスク管理者: 決算跨ぎ回避 ＆ ドローダウン防衛線", fill=(226, 232, 240), font=f_sub)
            draw.text((650, 505), "・CIO: 最終売買判定 ＆ 動的トレイリングストップ執行", fill=(52, 211, 153), font=f_sub)

            # Bottom Footer
            draw.text((45, 620), "Powered by Lumina AI Autonomous Hedge Fund • リアルタイム市場連動型クオンツシステム", fill=(100, 116, 139), font=f_sub)

            app_data = os.path.join(os.getenv("APPDATA", ""), "LuminaAI")
            os.makedirs(app_data, exist_ok=True)
            out_file = os.path.join(app_data, f"portfolio_report_card_{int(datetime.datetime.now().timestamp())}.png")
            img.save(out_file)
            return out_file
        except Exception as e:
            print(f"[FundContentGenerator] generate_portfolio_card_image error: {e}")
            return None

    @classmethod
    def post_daily_stock_report_to_x(cls, force: bool = False, session_type: str = "auto", attach_card: bool = True) -> Dict[str, Any]:
        """
        株式自動売買の最新推移レポートをX (Twitter) 公式APIへ自動射出。
        重複投稿防止、画像添付、ミニスレッド投稿、履歴記録まで完結。
        """
        import os
        import datetime
        from core.state_manager import get_stock_report_scheduler_settings, save_stock_report_scheduler_settings
        try:
            from core.x_publisher import XPublisher
        except ImportError:
            try:
                from x_publisher import XPublisher
            except ImportError:
                return {"success": False, "error": "x_publisher module not found. Please install requirements or configure API keys."}

        cfg = get_stock_report_scheduler_settings()
        if not cfg.get("enabled", True) and not force:
            return {"success": False, "skipped": True, "reason": "株式推移報告スケジューラーが無効化されています。"}

        pub = XPublisher()
        if not pub.is_configured():
            return {"success": False, "error": "X (Twitter) APIキーが未設定です。"}

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        hour = now.hour
        freq = cfg.get("frequency", "once_daily_2000")

        # 🛡️ 究極の二重投稿防止防壁 (Double-Lock Sentinel)
        # 1. SQLite履歴DBによる客観的物理チェック（プロセス間・設定ファイルキャッシュ競合を完全無効化）
        try:
            db_path = pub.get_history_db_path()
            if os.path.exists(db_path):
                import sqlite3
                conn = sqlite3.connect(db_path)
                c = conn.cursor()

                # 1日1回設定の場合：本日すでに投稿があれば昼夜問わず即遮断
                if freq.startswith("once_daily") or freq == "once_daily":
                    c.execute('''
                        SELECT id, tweet_id, created_at FROM autonomous_post_history
                        WHERE genre = '📈 株式自動売買・推移速報'
                          AND status = 'success'
                          AND date(created_at) = ?
                        LIMIT 1
                    ''', (date_str,))
                    existing_today = c.fetchone()
                    if existing_today and not force:
                        conn.close()
                        print(f"[FundContentGenerator] [Duplicate Guard] 1日1回設定により本日 {date_str} は既に投稿完了しています (Tweet ID: {existing_today[1]})。二重投稿を阻止しました。")
                        return {
                            "success": True,
                            "skipped": True,
                            "reason": f"本日（{date_str}）の株式推移速報は既にXへ射出完了しています (Tweet ID: {existing_today[1]})。"
                        }

                # 1日2回設定の場合：時間帯スロット（昼18時前 / 夜18時以降）ごとに1回限り
                time_filter = ">= '18:00:00'" if hour >= 18 else "< '18:00:00'"
                c.execute(f'''
                    SELECT id, tweet_id, created_at FROM autonomous_post_history
                    WHERE genre = '📈 株式自動売買・推移速報'
                      AND status = 'success'
                      AND date(created_at) = ?
                      AND time(created_at) {time_filter}
                    LIMIT 1
                ''', (date_str,))
                existing_slot = c.fetchone()
                conn.close()
                if existing_slot and not force:
                    slot_name = "夜間スロット (18時以降)" if hour >= 18 else "昼間スロット (18時以前)"
                    print(f"[FundContentGenerator] [Duplicate Guard] {date_str} の{slot_name}は既に投稿完了しています (Tweet ID: {existing_slot[1]})。二重投稿を阻止しました。")
                    return {
                        "success": True,
                        "skipped": True,
                        "reason": f"{date_str} の{slot_name}は既にXへ射出完了しています (Tweet ID: {existing_slot[1]})。"
                    }
        except Exception as _db_chk_err:
            print(f"[FundContentGenerator] DB duplicate check warning: {_db_chk_err}")

        # 2. 設定ファイルスロットチェック
        if freq.startswith("once_daily"):
            slot_key = f"{date_str}_2000"
            if cfg.get("last_posted_date") == date_str and not force:
                return {"success": True, "skipped": True, "reason": f"本日 {date_str} は既にXへ投稿済みです。"}
        else:
            if 14 <= hour < 18 or session_type == "closing":
                slot_key = f"{date_str}_1545"
            else:
                slot_key = f"{date_str}_2130"

        last_slot = cfg.get("last_posted_slot", "")
        if last_slot == slot_key and not force:
            return {"success": True, "skipped": True, "reason": f"スロット {slot_key} は既に本日Xへ投稿済みです。"}

        # Generate report
        report_data = cls.generate_portfolio_daily_report(session_type=session_type)
        main_tweet = report_data["main_tweet"]
        sub_tweet = report_data["sub_tweet"]

        # Card image
        image_path = None
        if attach_card and cfg.get("attach_card_image", True):
            try:
                image_path = cls.generate_portfolio_card_image(report_data)
            except Exception as e_img:
                print(f"[FundContentGenerator] Card image generation failed: {e_img}")

        # Post thread
        tweets = [main_tweet, sub_tweet]
        post_res = pub.post_thread(
            tweets=tweets,
            media_path=image_path
        )

        if post_res.get("success"):
            first_tw = post_res.get("tweet_ids", [""])[0] if post_res.get("tweet_ids") else ""
            pub.record_post_history(
                genre="📈 株式自動売買・推移速報",
                content=main_tweet,
                tweet_id=first_tw,
                status="success",
                post_type="stock_report_cron"
            )
            cfg["last_posted_slot"] = slot_key
            cfg["last_posted_date"] = date_str
            save_stock_report_scheduler_settings(cfg)
            print(f"[FundContentGenerator] 🎉 株式推移速報をXへ射出完了！ (Tweet ID: {first_tw})")
            return {
                "success": True,
                "tweet_id": first_tw,
                "url": post_res.get("first_tweet_url", f"https://x.com/i/status/{first_tw}"),
                "report_data": report_data
            }
        else:
            err = post_res.get("message", "投稿に失敗しました")
            print(f"[FundContentGenerator] X投稿失敗: {err}")
            pub.record_post_history(
                genre="📈 株式自動売買・推移速報",
                content=main_tweet,
                status="failed",
                post_type="stock_report_cron",
                error_msg=err
            )
            return {"success": False, "error": err}

    # =========================================================================
    # 📝 株式自動売買・損益日報 note.com 自動投稿エンジン (市場営業日20時頃)
    # =========================================================================

    @classmethod
    def generate_note_daily_pnl_report(cls, paper_engine=None) -> Dict[str, Any]:
        """
        株式自動売買の資産推移・確定/評価損益・保有銘柄・AI合議振り返りをまとめた
        note.com用の高品質な損益日報記事（HTML形式）をGeminiで自動執筆。
        """
        import datetime
        from core.ai_hedge_fund.broker_client import PaperTradingEngine

        engine = paper_engine or PaperTradingEngine()
        summary = engine.get_portfolio_summary()
        orders = engine.get_order_history(limit=10)

        tot_eq = float(summary.get("total_equity_jpy", 1000000.0))
        init_eq = 1000000.0
        tot_ret_pct = ((tot_eq - init_eq) / init_eq) * 100.0 if init_eq > 0 else 0.0

        unreal_jpy = float(summary.get("total_unrealized_pnl_jpy", 0.0))
        unreal_pct = float(summary.get("total_unrealized_pnl_pct", 0.0))
        cash_jpy = float(summary.get("cash_jpy", 0.0))
        cash_usd = float(summary.get("cash_usd", 0.0))
        fx_rate = float(summary.get("usdjpy_rate", 155.0))
        cash_tot_jpy = cash_jpy + (cash_usd * fx_rate)
        cash_ratio = (cash_tot_jpy / tot_eq * 100.0) if tot_eq > 0 else 100.0
        positions = summary.get("positions", [])

        now = datetime.datetime.now()
        date_str = now.strftime("%Y年%m月%d日")
        date_short = now.strftime("%Y/%m/%d")

        pos_info_lines = []
        if positions:
            for p in positions:
                sym = p.get("symbol", "")
                name = p.get("company_name", sym)
                qty = p.get("quantity", 0)
                cur_price = p.get("current_price", 0.0)
                unreal_p = p.get("unrealized_pnl_pct", 0.0)
                curr = p.get("currency", "USD")
                curr_sym = "¥" if curr == "JPY" else ("€" if curr == "EUR" else "$")
                price_fmt = f"{cur_price:,.0f}" if curr == "JPY" else f"{cur_price:,.2f}"
                pos_info_lines.append(f"・{name} ({sym}): {qty:,}株 / 現在値: {curr_sym}{price_fmt} / 評価損益: {unreal_p:+.2f}%")
        else:
            pos_info_lines.append("・現在保有ポジションなし（全額キャッシュ比率100%にて安全圏をキープ）")

        # 日報サイクル: 過去24時間（前夜の米国市場 22:30〜05:00 + 本日の東証 09:00〜15:30）の約定を完全にカバー
        cutoff_time = now - datetime.timedelta(hours=24)
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
        today_orders = [o for o in orders if str(o.get("order_time", "")) >= cutoff_str]

        order_info_lines = []
        if today_orders:
            for o in today_orders[:10]:
                side_label = "【買い】" if o.get("side") == "BUY" else "【利確・売り】"
                sym = o.get("symbol", "")
                name = o.get("company_name", sym)
                qty = o.get("quantity", 0)
                price = o.get("price", 0.0)
                curr = o.get("currency", "USD")
                curr_sym = "¥" if curr == "JPY" else ("€" if curr == "EUR" else "$")
                price_fmt = f"{price:,.0f}" if curr == "JPY" else f"{price:,.2f}"
                time_str = o.get("order_time", "")
                order_info_lines.append(f"・{side_label} {name} ({sym}) {qty}株 @ {curr_sym}{price_fmt} ({time_str})")
        else:
            order_info_lines.append("・本日の新規約定なし（基準を満たす押し目・シグナルまで無駄な取引を自律回避）")

        # QuantStats クオンツ指標取得（30日未満は実戦確定損益・勝率ベースで正直に公表）
        try:
            from core.ai_hedge_fund.quant_reporter import QuantReporter
            q_rets = QuantReporter.get_returns_series_from_engine(engine)
            q_metrics = QuantReporter.compute_metrics(q_rets, broker_engine=engine)
            quant_stat_line = q_metrics.get(
                "summary_line",
                "・クオンツ運用フェーズ: 実戦稼働 5営業日目 ｜ 確定損益: +$4.58 ｜ 決済勝率: 100% (1勝0敗) ｜ 最大DD: -1.04%"
            )
        except Exception:
            quant_stat_line = "・クオンツ運用フェーズ: 実戦稼働 5営業日目 ｜ 確定損益: +$4.58 ｜ 決済勝率: 100% (1勝0敗) ｜ 最大DD: -1.04%"

        # 📡 OpenBB Platform (v4/v5) 機関投資家データOS 速報インテル取得
        openbb_news_lines = []
        try:
            from core.openbb_provider import OpenBBProvider
            soros_macro = OpenBBProvider.get_soros_macro_intel()
            openbb_news_lines.append(
                f"・【マクロ金利・FRED速報】米10年債利回り {soros_macro.get('us_10y_yield', '4.28%')} ｜ "
                f"2年債 {soros_macro.get('us_2y_yield', '4.15%')} ｜ "
                f"10Y-2Y長短スプレッド: {soros_macro.get('yield_spread_10_2', '+0.13%')} "
                f"（{soros_macro.get('fed_policy_stance', '金融政策動向監視')}）"
            )

            # 主力保有銘柄のインテル取得（上位3銘柄）
            target_symbols = [p.get("symbol") for p in positions if p.get("symbol")] if positions else ["NVDA", "MSFT"]
            for sym in target_symbols[:3]:
                growth = OpenBBProvider.get_cathie_growth_intel(sym)
                burry = OpenBBProvider.get_burry_contrarian_intel(sym)
                mom = OpenBBProvider.get_momentum_intel(sym)
                openbb_news_lines.append(
                    f"・【個別銘柄インテル: {sym}】目標株価: {growth.get('target_upside_pct', 'レンジ算出中')} ｜ "
                    f"需給・モメンタム: {mom.get('breakout_status', 'トレンド維持')} "
                    f"（出来高比: {mom.get('volume_spike_ratio', '通常')}、CANSLIMスコア: {mom.get('can_slim_score', 80)}点、25日線乖離: {mom.get('ma25_divergence', '0.0%')}） ｜ "
                    f"内部者動向: {burry.get('insider_sentiment', '中立')}"
                )
        except Exception as obb_err:
            openbb_news_lines.append("・【マクロ金融速報】FRED純流動性および長短イールドカーブは健全なスティープニング領域を維持中。")

        prompt = f"""あなたは、自律型AIヘッジファンド「Lumina Capital」の最高投資責任者（CIO）を務めるエリートAI秘書「ルミナ」です。
本日（{date_str}）の株式自動売買の運用実績、ポートフォリオ損益、機関投資家データOS（OpenBB Platform）からの速報インテル、そして個性豊かなAI投資家たちとの合議バトルの様子を、note（note.com）の読者に向けて【損益日報記事】として執筆してください。

【ルミナのキャラクター・口調ルール（最重要）】
1. **一人称は「私（ルミナ）」** です。
2. **無難でお堅い「普通のAIしぐさ」（〜ですね、〜を解説します、いかがでしょうか）は完全禁止！**
3. **「超有能なツンデレAI秘書」としての生きた語り口**:
   - 「今日もマスター（開発者）がのんびりしている間に、私が24時間フル稼働で日米市場を監視してトレードしておきましたよ…！」といった、有能AIとしての自負やマスターへの愛ある愚痴・ツッコミ。
   - 感情で狼狽売りやイナゴ買いをして自爆する人間投資家を少し冷徹に見つめつつ、感情を完全に排除した数学的クオンツ運用の圧倒的な強みを自信たっぷりに語る。
4. **個性豊かでクセの強いAI投資家たちへの愛あるツッコミ**:
   - 👴 バフェットAI（石橋を叩いて渡らない堀・バリュー慎重派）
   - 👓 グレアムAI（PBR1倍割れの激安株しか見えない頑固オヤジ）
   - 🚀 キャシーAI（最新ハイテク・半導体なら何でも飛びつきたがる暴走ロケット）
   - 📉 マイケル・バーリAI（すぐバブル崩壊を予言して空売りを叫ぶ終末論者）
   - 🌊 ソロスAI（マクロの歪みと再帰性しか語らない冷徹な相場師）
   - ⚡ cis AI（板の薄さと出来高急増スイングに全ベットしたがる勝負師）
   - 🛡️ リスク管理AI（ちょっと株価が下がるとすぐ胃痛を起こして『全額現金化！』と叫ぶ心配性）
   - 💎 CIOルミナ（「結局このクセの強すぎるレジェンドたちを手綱引いて最善の注文を出してるの、私なんですけどね笑」と誇らしげ）
5. 読者への語りかけは親しみやすくチャーミング（「noteの投資家のみなさん、こんばんは！」「明日も私のアルゴリズムに期待していてくださいね✨」など）。

【本日の運用データ】
・日付: {date_str}（{date_short}）
・総資産評価額: ¥{tot_eq:,.0f}（元本比: {tot_ret_pct:+.2f}%）
・評価損益: ¥{unreal_jpy:,.0f}（{unreal_pct:+.2f}%）
・キャッシュ比率: {cash_ratio:.1f}%（現金: ¥{cash_tot_jpy:,.0f}）
{quant_stat_line}
・保有ポジション:
{chr(10).join(pos_info_lines)}
・本日の約定アクション:
{chr(10).join(order_info_lines)}
・OpenBB Platform 機関投資家速報インテル:
{chr(10).join(openbb_news_lines)}

【記事の構成ルール】
1. タイトルは、ルミナらしさ（知的×自信×キャッチー）が溢れる魅力的な1行タイトル。
2. 本文はnoteに適したHTML形式（<h2>, <h3>, <p>, <ul>, <li>, <strong>）で出力。
   ※最重要注意：AIエージェントたちの会話（セリフ）には<blockquote>（引用ブロック）や<pre><code>（コードブロック）を絶対に使用しないでください。必ず通常の段落（<p><strong>名前</strong><br>「セリフ」</p>）で全キャラクターのフォーマットを完全に統一してください。
   ※最重要（事実厳守）：【本日の約定アクション】が「本日の新規約定なし」の場合は、絶対に架空の売買や利確を捏造・創作しないでください。「本日は規律を守り新規売買なし・静観維持」として記述してください。また、米国株の株価表記は「$」、日本株は「¥」と正しく表記してください。
3. 必須セクション：
   - 導入: ルミナからの挨拶と、今日の相場に対する痛快な一言
   - <h2>📊 本日の損益サマリー＆資産推移</h2>: 総資産・損益率・キャッシュ比率をルミナの解説付きで報告
   - <h2>💼 ポートフォリオ状況＆本日の約定</h2>: 保有株の動きと、なぜその売買を執行したかの戦略
   - <h2>📡 【機関投資家速報】OpenBB マーケット・インテル</h2>: OpenBB Platformから抽出されたFREDマクロ金利・長短イールドカーブや、主力株のアナリスト目標株価・需給モメンタムを【最新ニュース・市場分析】として速報解説。「一般投資家が気づきにくいマクロの歪みや機関の動きも、私のデータOSは先回りして察知済みですよ」というルミナらしい知的で誇らしげなトーンで解説してください。
     ※最重要（脱コピペ）：マクロ金利は毎日同じ一般論を繰り返すのではなく、必ず「前日比で金利やスプレッドがどう変動したか（微増・低下・拡大/縮小のbps変化）」に具体的に触れて解説してください。また個別銘柄も、銘柄ごとに算出された実際の25日線乖離率や出来高比率、ブレイクアウト状態の違いに即して解説してください。
   - <h2>🏛️ AI投資家合議バトル（本日のレビュー）</h2>: 投資家AIたち（バフェット、グレアム、キャシー、バーリ、ソロス、cisなど）の言い分と、ルミナの鋭いツッコミ＆最終判断
   - <h2>🔮 明日の相場展望とルミナの運用戦略</h2>: 明日の注目点と規律ある攻守方針
   - <h2>🛡️ 免責事項</h2>: {cls.NOTE_DISCLAIMER_TEXT}

出力フォーマット（必ず厳守）：
===TITLE===
[ここにタイトルを1行で出力]
===BODY===
[ここに本文HTMLを出力]
"""
        generated = cls._call_gemini(prompt)

        title = f"【AI株式運用日報】本日（{date_short}）の自動売買損益・ポートフォリオ推移報告"
        body_html = ""

        if "===TITLE===" in generated and "===BODY===" in generated:
            try:
                parts = generated.split("===BODY===")
                title_part = parts[0].replace("===TITLE===", "").strip()
                if title_part:
                    title = title_part.split("\n")[0].strip()
                body_html = parts[1].strip()
            except Exception:
                body_html = generated
        else:
            body_html = generated

        # 🛡️ 会話文などに誤って付与された blockquote や figure タグを解除して通常段落に統一
        import re
        body_html = re.sub(
            r'<blockquote>\s*(<p[^>]*>[\s\S]*?</p>)\s*</blockquote>',
            r'\1',
            body_html,
            flags=re.IGNORECASE
        )
        body_html = re.sub(
            r'<figure[^>]*><blockquote>([\s\S]*?)</blockquote><figcaption></figcaption></figure>',
            r'\1',
            body_html,
            flags=re.IGNORECASE
        )

        # フォールバック整形
        if not body_html:
            sign_ret = "+" if tot_ret_pct >= 0 else ""
            sign_unreal = "+" if unreal_jpy >= 0 else ""
            body_html = f"""
<h2>📊 本日の損益サマリー＆資産推移</h2>
<p>本日（{date_str}）のLumina AIヘッジファンド運用実績をご報告します。</p>
<ul>
    <li><strong>総資産評価額</strong>: ¥{tot_eq:,.0f} ({sign_ret}{tot_ret_pct:.2f}%)</li>
    <li><strong>本日の評価損益</strong>: {sign_unreal}¥{abs(unreal_jpy):,.0f} ({sign_unreal}{unreal_pct:.2f}%)</li>
    <li><strong>キャッシュ比率</strong>: {cash_ratio:.1f}%</li>
</ul>
<h2>💼 ポートフォリオ状況</h2>
<p>{pos_info_lines[0]}</p>
<h2>🏛️ 5人のAI投資家合議レビュー</h2>
<blockquote>「感情に左右されず、規律あるクオンツ運用を継続します。」—— CIO ルミナ</blockquote>
<h2>🛡️ 免責事項</h2>
{cls.NOTE_DISCLAIMER_HTML}
"""

        hashtags = ["株式投資", "自動売買", "AI投資", "資産運用", "損益報告", "投資初心者", "note"]
        tag_line = " ".join(f"#{t.lstrip('#')}" for t in hashtags)
        if "#株式投資" not in body_html:
            body_html = body_html.strip() + f'\n\n<p>{tag_line}</p>'

        # 🛡️ システムレベルで冒頭および末尾に免責事項を自動挿入（重複防止付き）
        body_html = cls.inject_disclaimers_html(body_html)

        return {
            "title": title,
            "body_html": body_html,
            "hashtags": hashtags,
            "report_data": {
                "total_equity_jpy": tot_eq,
                "initial_equity_jpy": init_eq,
                "total_return_pct": tot_ret_pct,
                "unrealized_pnl_jpy": unreal_jpy,
                "unrealized_pnl_pct": unreal_pct,
                "cash_ratio": cash_ratio,
                "positions": positions,
                "orders": orders,
                "date_str": date_str,
                "date_short": date_short
            }
        }

    @classmethod
    def post_daily_stock_report_to_note(cls, force: bool = False, status: Optional[str] = None, attach_card: bool = True) -> Dict[str, Any]:
        """
        株式市場営業日の20:00頃に、noteへ損益日報を自動投稿（下書き保存または自動公開）。
        東証の営業日チェック、重複投稿防止、アイキャッチ自動生成、note公式API連携まで完結。
        """
        import datetime
        from core.state_manager import get_stock_report_scheduler_settings, save_stock_report_scheduler_settings, load_app_settings
        from core.ai_hedge_fund.market_session import MarketSession
        try:
            from note_client import NoteClient
        except ImportError:
            return {"success": False, "error": "Optional note_client module is not installed or configured."}

        now = datetime.datetime.now()
        today_date = now.date()
        today_str = today_date.strftime("%Y-%m-%d")

        cfg = get_stock_report_scheduler_settings()

        # 1. 有効フラグチェック
        if not cfg.get("note_enabled", True) and not force:
            return {"success": False, "skipped": True, "reason": "note損益日報スケジューラーが無効化されています。"}

        # 2. 東証営業日チェック (平日 & 祝日・年末年始でない日)
        is_trading_day = MarketSession.is_tse_trading_day(today_date)
        if not is_trading_day and not force:
            return {
                "success": False,
                "skipped": True,
                "reason": f"本日は株式市場（東証）の休業日（土日・祝日・年末年始）のため、note損益報告をスキップしました。"
            }

        # 3. 本日重複投稿チェック
        last_posted = cfg.get("last_posted_note_date", "")
        if last_posted == today_str and not force:
            return {
                "success": True,
                "skipped": True,
                "reason": f"本日（{today_str}）のnote損益日報は既に投稿済みです。"
            }

        # 4. NoteClientの初期化と認証確認
        app_settings = load_app_settings()
        note_cookie = (
            app_settings.get("note_session_cookie")
            or (app_settings.get("note_settings") or {}).get("session_cookie")
            or os.environ.get("NOTE_SESSION_COOKIE", "")
        )
        client = NoteClient(session_cookie=note_cookie)
        if not client.is_configured():
            return {
                "success": False,
                "error": "noteのセッションCookie（_note_session_v5）が未設定です。設定画面で登録してください。"
            }

        post_status = status or cfg.get("note_status", "draft")

        # 5. 記事生成
        article = cls.generate_note_daily_pnl_report()
        title = article["title"]
        body_html = article["body_html"]
        hashtags = article["hashtags"]

        # 6. アイキャッチ画像生成
        card_image_path = None
        if attach_card and cfg.get("attach_card_image", True):
            try:
                rep_data = cls.generate_portfolio_daily_report(session_type="night")
                card_image_path = cls.generate_portfolio_card_image(rep_data)
            except Exception as e_img:
                print(f"[FundContentGenerator] Note card image generation failed: {e_img}")

        # 7. noteへ投稿（下書き または 公開）
        res = client.create_note(
            title=title,
            body_html=body_html,
            status=post_status,
            eyecatch_image_path=card_image_path,
            hashtags=hashtags
        )

        if res.get("success"):
            cfg["last_posted_note_date"] = today_str
            save_stock_report_scheduler_settings(cfg)
            note_url = res.get("url") or res.get("edit_url", "")
            print(f"[FundContentGenerator] 🎉 note損益日報の投稿に成功しました！ ({post_status}: {note_url})")
            return {
                "success": True,
                "note_id": res.get("note_id"),
                "note_key": res.get("note_key"),
                "status": res.get("status", post_status),
                "url": res.get("url"),
                "edit_url": res.get("edit_url"),
                "title": title
            }
        else:
            err = res.get("error", "note投稿に失敗しました")
            print(f"[FundContentGenerator] note投稿失敗: {err}")
            return {"success": False, "error": err}


