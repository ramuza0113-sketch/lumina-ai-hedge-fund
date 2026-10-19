import os
import re
import json
import sqlite3
import hashlib
from typing import Optional, Dict, Any

AGENT_NAME_MAP = {
    "ウォーレン・バフェット": "Warren Buffett",
    "ベンジャミン・グレアム": "Benjamin Graham",
    "キャシー・ウッド": "Cathie Wood",
    "マイケル・バーリ": "Michael Burry",
    "ジョージ・ソロス": "George Soros",
    "ウィリアム・オニール": "William O'Neil",
    "cis / BNF風（日本株スイング）": "cis / BNF Swing Trader",
    "リスク管理者 (CRO)": "Chief Risk Officer (CRO)",
    "モメンタム投資家": "Momentum / Technical Analyst",
    "クオンツ・AIアナリスト": "Quant / Valuation Analyst"
}

AGENT_TITLE_MAP = {
    "価値創造・堀の番人": "Guardian of Moat & Value",
    "安全域・深層バリュー分析官": "Margin of Safety & Deep Value",
    "破壊的イノベーション探求官": "Disruptive Innovation Explorer",
    "深層脆弱性・バブル警戒官": "Vulnerability & Bubble Sentinel",
    "マクロ心理・再帰性戦略官": "Macro Reflexivity Strategist",
    "CANSLIM・成長株モメンタム官": "CANSLIM Growth Momentum",
    "需給・板読みモメンタム官": "Order Flow & Tape Reading",
    "資産防衛・悪魔の代弁者": "Capital Defense & Devil's Advocate",
    "資産防衛・ドローダウン監視官": "Capital Defense & Drawdown Monitor"
}

COMPANY_NAME_MAP = {
    "アクセンチュア": "Accenture plc",
    "アクセル": "AXELL Corporation",
    "日本取引所グループ": "Japan Exchange Group (JPX)",
    "太陽誘電": "Taiyo Yuden Co., Ltd.",
    "セブン＆アイ・ホールディングス": "Seven & i Holdings Co., Ltd.",
    "キーウェアソリューションズ": "Keyware Solutions Inc.",
    "グラファイトデザイン": "Graphite Design Inc.",
    "トーセイ": "Tosei Corporation",
    "ソディック": "Sodick Co., Ltd.",
    "INGグループ": "ING Group",
    "レオパレス21": "Leopalace21 Corporation",
    "三協立山": "Sankyo Tateyama, Inc.",
    "オンワードホールディングス": "Onward Holdings Co., Ltd.",
    "ローツェ": "Rorze Corporation",
    "三菱重工業": "Mitsubishi Heavy Industries, Ltd.",
    "川崎重工業": "Kawasaki Heavy Industries, Ltd.",
    "フジクラ": "Fujikura Ltd.",
    "住友電気工業": "Sumitomo Electric Industries, Ltd.",
    "コマツ": "Komatsu Ltd.",
    "三菱商事": "Mitsubishi Corporation",
    "トヨタ自動車": "Toyota Motor Corporation",
    "ソニーグループ": "Sony Group Corporation",
    "日立製作所": "Hitachi, Ltd.",
    "東京エレクトロン": "Tokyo Electron Limited",
    "アッヴィ": "AbbVie Inc.",
    "マイクロン": "Micron Technology, Inc.",
    "メルク": "Merck & Co., Inc.",
    "オーケストラホールディングス": "Orchestra Holdings Inc."
}

# Pre-computed high-fidelity hedge-fund translations for key historical archives
STATIC_TRANSLATIONS: Dict[str, str] = {
    # Mandates
    "mandate_fib_stop_loss": "Strictly enforce Fibonacci optimal stop-loss at -13.0% (Entry x 0.87) as an absolute citadel. Premature stop-hunting from intraday noise is strictly prohibited.",
    "mandate_veto_defense": "Respect the Chief Risk Officer's (CRO) absolute veto power (VETO). No matter how high the score, pass on trades with excessive concentration or geopolitical risk.",
    "mandate_market_hours": "During 22:30 - 05:00 JST (US market core hours), pause heavy batch processing and dedicate resources to order-book monitoring, limit orders, and CRO risk defense.",
    "mandate_opportunity_cost": "To avoid opportunity cost, do not wait for prolonged live seasoning of promising hypotheses; statistically validate them same-day via 2-year Walk-Forward backtesting before deployment.",

    # Sources
    "マスター直接指示": "Master Direct Directive",
    "マスター管理画面指定": "Master Admin Console",
    "チャット指示": "Chat Directive",

    # RARE Council (Council #61)
    "前回の合議で提起された債務超過・大幅FCF赤字という財務脆弱性が依然として解消されておらず、直近ヘッドラインでも急落リスクが顕在化している。トップラインの成長は見られるものの安全域が皆無であり、資本毀損リスクを回避するため投資見送り（ポジションゼロでの静観）を維持する。":
        "The financial fragility of negative equity and substantial FCF deficits raised in the previous council remains unresolved, and recent headlines show emerging plunge risks. Although top-line growth is observable, margin of safety is nonexistent. To prevent capital impairment, we maintain our recommendation to pass on this investment (observing with zero position).",

    "前回指摘した構造的課題は何一つ改善されていない。営業利益率マイナス35%、FCFは年間2.2億ドル以上の純流出であり、純資産はマイナス（債務超過）だ。希少疾患向けバイオに独占性があったとしても、自力でキャッシュを生み出せない企業に持続的な『経済的な堀』は存在しない。希薄化増資に依存し続けるビジネスモデルは、長期保有に到底値しない。":
        "Not a single structural flaw raised in our prior review has improved. Operating margin sits at -35%, FCF suffers annual net outflows exceeding $220M, and net tangible assets are negative (insolvency). Even with monopolies in rare disease biotech, a business unable to generate self-sustaining cash has no durable 'Economic Moat'. Relying perpetually on dilutive secondary offerings is fundamentally unworthy of long-term ownership.",

    "純資産がマイナス4.95倍と自己資本が毀損しており、グレアム数は算出不能、実績PERも欠損だ。流動比率1.73倍で短期の支払い能力を辛うじて維持しているに過ぎず、『安全の原則』から最も遠い投機的状態にある。直近のニュースでも時間外での急落シグナルが観測されており、元本毀損リスクが極めて高く、断固として拒否する。":
        "Shareholders' equity is severely impaired with negative net assets, rendering the Graham Number incalculable and trailing P/E negative. A current ratio of 1.73 barely maintains short-term solvency, placing this asset in a speculative regime furthest from our 'Margin of Safety'. After-hours plunge signals in recent news reinforce an unacceptable probability of principal impairment. We reject this proposal emphatically.",

    "希少・超希少遺伝病に対するパイプラインとCrysvita等の商業化実績、そしてYoY売上高28.1%成長というトップラインの拡大は評価できます。優先審査バウチャー（PRV）の市場価値など隠れた知財アセットも豊富です。しかし、直近で時間外の大幅下落報道が出るなどボラティリティが81%を超えており、カタリストの不透明感が払拭されるまでは積極買いには動けません。":
        "We acknowledge the promising rare/ultra-rare genetic disease pipeline, commercial traction with Crysvita, and 28.1% YoY top-line expansion. Intangible assets like Priority Review Vouchers (PRV) offer hidden intellectual value. However, annualized volatility exceeds 81% alongside steep after-hours drops. Until catalyst opacity lifts, we cannot justify an aggressive buy posture.",

    "年率ボラティリティ81.8%、14日ATRは0.80ドル（5.47%）に達し、外部データでも急落懸念が報じられています。フィボナッチ最適値（-13.0%）に基づく防壁ラインは12.75ドル付近ですが、52週安値（12.73ドル）の岩盤を割り込むリスクが高まっています。キャッシュバーンの持続とバイオ特有のクリティカルな不確実性を鑑みれば、新規エントリーは厳禁です。":
        "Annualized volatility has surged to 81.8% and 14-day ATR stands at $0.80 (5.47%), with external sentiment signaling elevated drawdown risks. The defensive barrier calculated from the Fibonacci optimal threshold (-13.0%) is near $12.75, risking a breach beneath the 52-week low ($12.73). Given continuous cash burn and biotech-specific tail risks, initiating new positions is strictly prohibited.",

    # Tokyo Electron (Council #67 & #65)
    "AI半導体需要に伴う高い成長性と再帰的モメンタムは評価に値するものの、実績PER45倍超に安全域は皆無であり、過熱感と出来高の乖離は反落リスクを強く示唆している。さらにリスク管理者による絶対的拒否権が発動された現状に鑑みれば、急変警戒下での追随買いは明白な規律違反である。構造的優位性を認めつつも投機的熱狂から一線を画し、資本保全を至上命題として新規建てを完全に凍結、冷静に調整局面を待つのが至当である。":
        "Although high growth and reflexive momentum driven by AI semiconductor demand deserve merit, trailing P/E above 45x offers zero margin of safety, and volume divergence strongly warns of pullback risk. Given the CRO's active absolute veto, chasing this rally violates strict risk discipline. We freeze new entries to prioritize capital preservation and patiently await a healthier pullback.",

    "卓越した収益力と株主還元を背景とする強烈な成長モメンタムは評価に値するが、実績ＰＥＲ45倍超かつ過熱圏にある価格は安全域を著しく欠く。加えて、市場急変とボラティリティ拡大を警告するＣＲＯの絶対的拒否権が発動された現状、元本保全の投資規律を最優先すべき局面である。いかに魅惑的な成長物語であっても暴落リスクを看過することは許されず、最高投資責任者として規律に従い新規ポジション建てを完全凍結と裁定する。（199文字）":
        "Outstanding profitability and shareholder returns provide strong momentum, but a valuation above 45x P/E severely lacks a margin of safety. With the CRO exercising an absolute veto warning of abrupt volatility, capital preservation remains our paramount mandate. We mandate a complete freeze on new positions.",

    # Micron (Council #66)
    "AI需要に伴う圧倒的成長性を評価する声はあるものの、PBR11.53倍という歴史的割高感と業績循環のピーク懸念、出来高低迷に伴うモメンタム喪失は看過できない。さらにガンマフリップ割れによる急激な価格急変リスクを重く見出し、資本の恒久的毀損を防ぐべくCROの拒否権発動を支持する。市場の陶酔に惑わされることなく、流動性の脆弱性と安全域の欠如を最優先に勘案し、現局面における新規ポジション形成を厳格に凍結する。":
        "While AI demand fuels extraordinary growth, an unprecedented P/B of 11.53x and cyclical peak concerns cannot be ignored. A breach beneath the Gamma Flip level introduces tail-risk volatility, prompting full CRO veto backing to safeguard capital from permanent impairment. New position initiation is strictly frozen.",

    # Accenture (Council #63)
    "堅牢な事業基盤（Moat）とFCF創出力（111.8億ドル）を有し、予想PER 12.7倍と妥当に収まっている。AI需要による受注高成長（+46.4%）も確認され、押し目構築の好機と判断する。":
        "Possessing a fortress business moat and massive FCF generation ($11.18B), valuation remains attractive at a forward P/E of 12.7x. AI bookings expansion (+46.4%) confirms strong momentum, presenting a prime opportunity for dip-buying.",

    # Action labels
    "🚨 CRO拒否権発動（新規建て完全凍結）": "🚨 CRO Veto Invoked (New Positions Fully Frozen)",
    "買い推奨": "BUY Recommendation",
    "積極買い推奨（買い増し）": "STRONG BUY (Add on Dips)",
    "積極買い推奨": "STRONG BUY Recommendation",
    "見送り・静観推奨": "HOLD / Pass (Stand Aside)",
    "様子見・保有継続": "HOLD / Maintain Position",
    "様子見・押し目待ち": "HOLD / Awaiting Dip",
    "様子見・買い見送り": "HOLD / Pass on Buying",
    "慎重買い（ディープバリュー枠）": "Cautious BUY (Deep Value)",
    "選別的買い推奨": "Selective BUY Recommendation",
    "買い推奨（押し目構築）": "BUY Recommendation (Dip Accumulation)",
    "押し目買い推奨": "BUY on Dips Recommendation",
    "中立・様子見（好転待ち）": "Neutral / Stand Aside (Awaiting Turnaround)",
    "規律的買い推奨": "Disciplined BUY Recommendation"
}


class TranslationEngine:
    _db_path = None

    @classmethod
    def _get_db_path(cls) -> str:
        if cls._db_path is None:
            base_dir = os.getenv('APPDATA') or os.path.expanduser('~/.local/share')
            app_data_dir = os.path.join(base_dir, 'LuminaAI')
            os.makedirs(app_data_dir, exist_ok=True)
            cls._db_path = os.path.join(app_data_dir, 'translation_cache.db')
            cls._init_db()
        return cls._db_path

    @classmethod
    def _init_db(cls):
        try:
            conn = sqlite3.connect(cls._db_path)
            with conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS translation_cache (
                    text_hash TEXT PRIMARY KEY,
                    target_lang TEXT,
                    source_text TEXT,
                    translated_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.close()
        except Exception:
            pass

    @classmethod
    def _lookup_cache(cls, text: str, target_lang: str) -> Optional[str]:
        # 1. Static dict check
        clean = text.strip()
        if clean in STATIC_TRANSLATIONS:
            return STATIC_TRANSLATIONS[clean]

        # 2. SQLite cache check
        try:
            db_p = cls._get_db_path()
            th = hashlib.sha256((target_lang + ":" + clean).encode('utf-8')).hexdigest()
            conn = sqlite3.connect(db_p)
            cur = conn.cursor()
            cur.execute("SELECT translated_text FROM translation_cache WHERE text_hash = ?", (th,))
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                res = row[0].strip()
                if target_lang == "en" and any('\u3000' <= ch <= '\u9fff' for ch in res):
                    return None
                return res
        except Exception:
            pass
        return None

    @classmethod
    def _save_cache(cls, text: str, target_lang: str, translated: str):
        if not translated:
            return
        if target_lang == "en" and any('\u3000' <= ch <= '\u9fff' for ch in translated):
            return
        try:
            db_p = cls._get_db_path()
            clean = text.strip()
            th = hashlib.sha256((target_lang + ":" + clean).encode('utf-8')).hexdigest()
            conn = sqlite3.connect(db_p)
            with conn:
                conn.execute("""
                INSERT OR REPLACE INTO translation_cache (text_hash, target_lang, source_text, translated_text)
                VALUES (?, ?, ?, ?)
                """, (th, target_lang, clean, translated.strip()))
            conn.close()
        except Exception:
            pass

    @classmethod
    def translate_text(cls, text: str, target_lang: str = "en", api_key: str = "") -> str:
        """
        Translates Japanese text to English.
        Prioritizes static dictionary -> SQLite cache -> Gemini LLM API -> Heuristic replacer.
        """
        if target_lang == "ja" or not text or not text.strip():
            return text

        # Check if text contains Japanese characters (hiragana, katakana, kanji)
        if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text):
            return text

        clean = text.strip()

        # Cache check
        cached = cls._lookup_cache(clean, target_lang)
        if cached:
            return cached

        # Fast Gemini LLM Translation
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            try:
                from core.state_manager import load_app_settings
                cfg = load_app_settings()
                key = cfg.get("google_api_key", "")
            except Exception:
                pass

        if key:
            try:
                from google import genai
                client = genai.Client(api_key=key)
                prompt = (
                    "Translate the following Japanese investment analysis / reflection text to natural, professional English "
                    "fit for an elite Wall Street quantitative hedge fund dashboard. "
                    "Preserve all ticker symbols, numerical figures, percentages, and metrics. "
                    "Output ONLY the direct English translation without any conversational preamble or quotes.\n\n"
                    + clean
                )
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if resp and resp.text and resp.text.strip():
                    translated = resp.text.strip()
                    cls._save_cache(clean, target_lang, translated)
                    return translated
            except Exception:
                pass

        # Fallback fast Google web translation
        web_res = cls._translate_via_web_fallback(clean, target_lang)
        if web_res and not any('\u3000' <= ch <= '\u9fff' for ch in web_res):
            cls._save_cache(clean, target_lang, web_res)
            return web_res

        # Fallback heuristic translation
        translated = cls._heuristic_translate(clean)
        cls._save_cache(clean, target_lang, translated)
        return translated

    @classmethod
    def _translate_via_web_fallback(cls, s: str, target_lang: str = "en") -> Optional[str]:
        if not s or not any('\u3000' <= ch <= '\u9fff' for ch in s):
            return s
        try:
            import urllib.parse
            import requests
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ja&tl={target_lang}&dt=t&q={urllib.parse.quote(s.strip())}"
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                parts = resp.json()[0]
                translated = "".join([p[0] for p in parts if p[0]]).strip()
                if translated and not any('\u3000' <= ch <= '\u9fff' for ch in translated):
                    return translated
        except Exception:
            pass
        return None

    @classmethod
    def _heuristic_translate(cls, s: str) -> str:
        res = s
        repls = [
            ("目標株価:", "Target Price:"),
            ("目標株価", "Target Price"),
            ("損切り:", "Stop-loss:"),
            ("損切りライン:", "Stop-Loss Level:"),
            ("配分上限:", "Max Allocation:"),
            ("CIO投資方針:", "CIO Investment Thesis:"),
            ("フィボナッチ最適損切りライン", "Fibonacci optimal stop-loss line"),
            ("到達による規律ある損切り。損失を最小限に抑え次回への教訓とする。", "Disciplined stop-loss executed upon reaching threshold. Minimized loss and logged as institutional lesson for next cycle."),
            ("機関の上値抵抗壁 Call Wall", "Institutional Call Wall ceiling"),
            ("到達で半分利確ロック。残りは買値/Put Wallストップでガンマ・スクイーズ突破をノーリスク追随。", "Half profit locked upon reaching Call Wall. Remainder trailing gamma squeeze risk-free with entry / Put Wall stop."),
            ("手動全株売却", "Manual Full Liquidation"),
            ("手動買い発注", "Manual Buy Order"),
            ("手動成行買い", "Manual Market Buy"),
            ("手動成行売り", "Manual Market Sell"),
            ("損益:", "PnL:"),
            ("営業利益率", "Operating margin"),
            ("純資産", "Net assets"),
            ("債務超過", "insolvency/negative equity"),
            ("経済的な堀", "Economic Moat"),
            ("安全域", "Margin of Safety"),
            ("元本毀損リスク", "capital impairment risk"),
            ("投資見送り", "pass on investment"),
            ("積極買い", "aggressive buying"),
            ("新規エントリーは厳禁", "new entry strictly prohibited"),
            ("特記事項なし", "No special notes.")
        ]
        for jp, en in repls:
            res = res.replace(jp, en)
        for jp_name, en_name in AGENT_NAME_MAP.items():
            res = res.replace(jp_name, en_name)
        for jp_co, en_co in COMPANY_NAME_MAP.items():
            res = res.replace(jp_co, en_co)
        return res

    @classmethod
    def localize_agent_name(cls, name: str, lang: str = "en") -> str:
        if lang == "ja" or not name:
            return name
        return AGENT_NAME_MAP.get(name.strip(), name)

    @classmethod
    def localize_agent_title(cls, title: str, lang: str = "en") -> str:
        if lang == "ja" or not title:
            return title
        return AGENT_TITLE_MAP.get(title.strip(), title)

    @classmethod
    def localize_company_name(cls, name: str, symbol: str = "", lang: str = "en") -> str:
        if lang == "ja" or not name:
            return name
        clean = name.strip()
        if clean in COMPANY_NAME_MAP:
            return COMPANY_NAME_MAP[clean]
        for jp, en in COMPANY_NAME_MAP.items():
            if jp in clean:
                clean = clean.replace(jp, en)
        return clean

    @classmethod
    def localize_mandate(cls, m: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
        if lang == "ja" or not m:
            return m
        loc = dict(m)
        mid = loc.get("mandate_id", "")
        if mid in STATIC_TRANSLATIONS:
            loc["rule_text"] = STATIC_TRANSLATIONS[mid]
        else:
            loc["rule_text"] = cls.translate_text(loc.get("rule_text", ""), lang)
        
        src = loc.get("source", "")
        if src in STATIC_TRANSLATIONS:
            loc["source"] = STATIC_TRANSLATIONS[src]
        elif "マスター直接" in src:
            loc["source"] = "Master Direct Directive"
        elif "マスター管理画面" in src:
            loc["source"] = "Master Admin Console"
        elif "チャット" in src:
            loc["source"] = "Chat Directive"
        return loc

    @classmethod
    def localize_trade_memory(cls, tm: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
        if lang == "ja" or not tm:
            return tm
        loc = dict(tm)
        loc["company_name"] = cls.localize_company_name(loc.get("company_name", ""), loc.get("symbol", ""), lang)
        raw_lesson = loc.get("lesson_learned", "")
        if raw_lesson:
            lesson_translated = re.sub(
                r'目標株価:\s*([0-9.,]+)\s*/\s*損切り:\s*([0-9.,]+)',
                r'Target: \1 / Stop-Loss: \2',
                raw_lesson
            )
            lesson_translated = cls.translate_text(lesson_translated, lang)
            loc["lesson_learned"] = lesson_translated
        return loc

    @classmethod
    def localize_council_record(cls, cr: Dict[str, Any], lang: str = "en", api_key: str = "") -> Dict[str, Any]:
        if lang == "ja" or not cr:
            return cr
        loc = dict(cr)
        loc["company_name"] = cls.localize_company_name(loc.get("company_name", ""), loc.get("symbol", ""), lang)
        loc["action_label"] = cls.localize_action_label(loc.get("action_label", ""), loc.get("action", ""), lang)
        if loc.get("thesis_summary"):
            loc["thesis_summary"] = cls.translate_text(loc["thesis_summary"], lang, api_key)
        
        diags = loc.get("dialogues", [])
        if diags:
            loc_diags = []
            for d in diags:
                d_loc = dict(d)
                d_loc["name"] = cls.localize_agent_name(d_loc.get("name", ""), lang)
                d_loc["title"] = cls.localize_agent_title(d_loc.get("title", ""), lang)
                if d_loc.get("dialogue"):
                    d_loc["dialogue"] = cls.translate_text(d_loc["dialogue"], lang, api_key)
                loc_diags.append(d_loc)
            loc["dialogues"] = loc_diags

        cd = loc.get("cross_debate", {})
        if cd and cd.get("occurred"):
            cd_loc = dict(cd)
            cd_loc["bear_name"] = cls.localize_agent_name(cd_loc.get("bear_name", ""), lang)
            cd_loc["bull_name"] = cls.localize_agent_name(cd_loc.get("bull_name", ""), lang)
            if cd_loc.get("turn1_attack"):
                cd_loc["turn1_attack"] = cls.translate_text(cd_loc["turn1_attack"], lang, api_key)
            if cd_loc.get("turn2_defense"):
                cd_loc["turn2_defense"] = cls.translate_text(cd_loc["turn2_defense"], lang, api_key)
            loc["cross_debate"] = cd_loc
        return loc

    @classmethod
    def localize_action_label(cls, label: str, action: str = "", lang: str = "en") -> str:
        if lang == "ja" or not label:
            return label
        clean = label.strip()
        if clean in STATIC_TRANSLATIONS:
            return STATIC_TRANSLATIONS[clean]
        if "拒否権" in clean or "VETO" in clean.upper():
            return "🚨 CRO Veto Invoked (New Positions Fully Frozen)"
        if "買い増し" in clean:
            return "STRONG BUY (Add on Dips)"
        if "積極買い" in clean:
            return "STRONG BUY Recommendation"
        if "慎重買い" in clean:
            return "Cautious BUY (Deep Value)"
        if "押し目買い" in clean or "押し目" in clean:
            return "BUY on Dips Recommendation"
        if "見送り" in clean or "静観" in clean:
            return "HOLD / Pass (Stand Aside)"
        if "様子見" in clean or "保有継続" in clean:
            return "HOLD / Maintain Position"
        if "買い推奨" in clean:
            return "BUY Recommendation"
        
        act_map = {
            "BUY": "STRONG BUY",
            "ACCUMULATE": "ACCUMULATE / DIP BUY",
            "HOLD": "HOLD / NEUTRAL",
            "REDUCE": "REDUCE",
            "SELL": "STRONG SELL"
        }
        if action and action in act_map:
            return act_map[action]
        return cls.translate_text(label, lang)

