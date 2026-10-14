# -*- coding: utf-8 -*-
import os
import time
import json
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.ai_hedge_fund.market_data_feed import MarketDataFeed
from core.ai_hedge_fund.news_feed import NewsFeed
from core.ai_hedge_fund.sec_insider_feed import SecInsiderFeed

class MarketScreener:
    """
    Lumina AI Market Screener & Autonomous Stock Hunter (v3.42)
    Scans Japanese (TSE) and US (NASDAQ/NYSE) markets for top investment opportunities:
    1. Defense & Energy / Heavy Industry (三菱重工、川崎重工、IHI、AI電力フジクラ、Vistra)
    2. AI, Semiconductor & Big Tech (NVIDIA、マイクロソフト、ディスコ、アドバンテスト)
    3. Buffett Moat, 5 Big Trading Houses & High Dividend (商社5社、信越化学、メガバンク)
    4. Graham Deep Value (PBR1倍割れ改善、製鉄、ホンダ)
    5. User Custom Watchlist (ユーザー独自登録銘柄の最優先巡回)
    """

    UNIVERSE = {
        "DEFENSE_ENERGY": [
            {"symbol": "7011.T", "name": "三菱重工業", "category": "防衛首位・航空宇宙・ガスタービン", "thesis": "防衛予算倍増と次世代原発・脱炭素タービンの世界的需要。モメンタム最強銘柄"},
            {"symbol": "7012.T", "name": "川崎重工業", "category": "防衛・航空機エンジン・水素", "thesis": "防衛省大型受注と民間航空機エンジン好調。PBR改善と業績急拡大"},
            {"symbol": "7013.T", "name": "IHI", "category": "防衛・ジェットエンジン・宇宙", "thesis": "民間航空機スペアパーツ需要旺盛。防衛装備移転緩和の国策恩恵"},
            {"symbol": "5803.T", "name": "フジクラ", "category": "AIデータセンター電線・光ファイバー", "thesis": "生成AI向け超多心光コネクタで世界独占的シェア。株価爆発的急騰トレンド"},
            {"symbol": "5802.T", "name": "住友電気工業", "category": "電力インフラ・ワイヤーハーネス", "thesis": "全米・欧州の送電網更新需要とAI電力特需。高ROE体質へ転換"},
            {"symbol": "6301.T", "name": "コマツ", "category": "建機世界2位・資源インフラ", "thesis": "IoT建機Komtraxによる高収益フリート。鉱山向け資源需要と安定増配"},
            {"symbol": "VST", "name": "Vistra Corp", "category": "AIデータセンター原子力電力", "thesis": "メガテック向けクリーン電力長期契約。S&P500年間上昇率トップクラス"},
            {"symbol": "RTX", "name": "RTX Corporation", "category": "防衛・ミサイル・航空宇宙首位", "thesis": "ペイトリオットミサイル等の防衛受注残高が過去最高。世界的安全保障需要"},
            {"symbol": "LMT", "name": "Lockheed Martin", "category": "戦闘機・ステルス・宇宙防衛", "thesis": "F-35戦闘機のグローバル配備と強固な政府予算バックボーン。安定高配当"},
            {"symbol": "GE", "name": "GE Aerospace", "category": "航空機エンジン・保守サービス", "thesis": "スピンオフ完了で超高収益航空宇宙専業へ。営業利益率20%超の高成長"},
            {"symbol": "CCJ", "name": "Cameco", "category": "ウラン燃料世界最大手", "thesis": "データセンター向け次世代原発再評価によるウラン供給不足と長期契約価格高騰"}
        ],
        "AI_GROWTH": [
            {"symbol": "NVDA", "name": "NVIDIA", "category": "生成AI半導体・GPU絶対王者", "thesis": "データセンター向けAIインフラの9割を独占。Blackwell需要爆発"},
            {"symbol": "MSFT", "name": "Microsoft", "category": "Azureクラウド & OpenAI筆頭出資", "thesis": "Copilotとクラウドの法人浸透。巨額FCFとAIマネタイズ最前線"},
            {"symbol": "GOOGL", "name": "Alphabet (Google)", "category": "Gemini AI & 検索・YouTube", "thesis": "TPU（独自AIチップ）内製化と圧倒的計算リソース。割安なPER水準"},
            {"symbol": "META", "name": "Meta Platforms", "category": "オープンソースAI (Llama) & SNS", "thesis": "AIレコメンドによる広告売上高成長。30億人のユーザー基盤"},
            {"symbol": "AMZN", "name": "Amazon", "category": "AWSクラウド & Eコマース自動化", "thesis": "AWSの成長再加速とロボティクス自動化によるマージン拡大"},
            {"symbol": "PLTR", "name": "Palantir Technologies", "category": "企業・防衛向けAIプラットフォーム", "thesis": "AIP（エンタープライズAI）の導入加速。S&P500採用で機関マネー流入"},
            {"symbol": "AVGO", "name": "Broadcom", "category": "カスタムAI半導体 (ASIC) & VMware", "thesis": "大手テック独自AIチップの受託開発とVMware買収による高収益化"},
            {"symbol": "TSLA", "name": "Tesla", "category": "EV・自律走行FSD・人型ロボット", "thesis": "ロボタクシー＆OptimusによるAI・フィジカルAI企業へのパラダイムシフト"},
            {"symbol": "AMD", "name": "Advanced Micro Devices", "category": "AIアクセラレータ (MI300) & CPU", "thesis": "NVIDIA対抗の有力急先鋒。データセンター向けシェア拡大期待"},
            {"symbol": "ARM", "name": "Arm Holdings", "category": "半導体アーキテクチャIP", "thesis": "スマートフォン・AIサーバーの消費電力低減に不可欠。ライセンス料率上昇"},
            {"symbol": "6146.T", "name": "ディスコ", "category": "半導体切断・研削装置世界首位", "thesis": "先端AI半導体（HBM）製造に不可欠な精密加工装置。営業利益率40%超"},
            {"symbol": "6857.T", "name": "アドバンテスト", "category": "半導体テスター世界首位", "thesis": "GPU・HBMメモリの複雑化でテスター需要爆発。AI波及の最大恩恵"},
            {"symbol": "8035.T", "name": "東京エレクトロン", "category": "半導体前工程製造装置世界トップ", "thesis": "成膜・コータデベロッパ世界首位級。2nmプロセス移行に必須"},
            {"symbol": "6501.T", "name": "日立製作所", "category": "IT×エネルギー・Lumada高収益化", "thesis": "重電からDX・電力グリッド世界首位級へ変貌。時価総額急伸"},
            {"symbol": "6758.T", "name": "ソニーグループ", "category": "CMOSイメージセンサ・ゲーム・音楽", "thesis": "スマホ用先端センサ独占とIPコンテンツの世界的強み"},
            {"symbol": "9984.T", "name": "ソフトバンクグループ", "category": "Arm筆頭株主 & AI投資ファンド", "thesis": "Arm株の含み益爆発とASICチップ・AIインフラ構想の加速"},
            {"symbol": "3778.T", "name": "さくらインターネット", "category": "国産生成AIクラウド", "thesis": "政府認定クラウド。経産省補助金によるGPU大規模増強"}
        ],
        "VALUE_DIVIDEND": [
            {"symbol": "8058.T", "name": "三菱商事", "category": "総合商社首位・累進配当", "thesis": "バフェット保有銘柄。強固な資源・非資源CFと積極的自社株買い"},
            {"symbol": "8001.T", "name": "伊藤忠商事", "category": "総合商社・非資源首位", "thesis": "非資源比率が高く景気耐性抜群。高ROEと安定配当成長"},
            {"symbol": "8031.T", "name": "三井物産", "category": "総合商社・資源・エネルギー強み", "thesis": "LNG・鉄鉱石の優良権益と潤沢なフリーキャッシュフロー"},
            {"symbol": "8053.T", "name": "住友商事", "category": "総合商社・メディア・金属", "thesis": "バフェット投資先。高配当利回りとPBR1倍超えに向けた資産入替"},
            {"symbol": "8002.T", "name": "丸紅", "category": "総合商社・穀物・電力アグリ", "thesis": "アグリ事業の世界的強みと低PER・連続増配トレンド"},
            {"symbol": "9432.T", "name": "日本電信電話 (NTT)", "category": "通信インフラ・ディフェンシブ", "thesis": "国策インフラの絶対的ワイド・モート。安定高配当とIOWN構想"},
            {"symbol": "9433.T", "name": "KDDI", "category": "通信・ローソン提携・DX", "thesis": "20年以上連続増配。強固な営業利益率20%水準"},
            {"symbol": "8306.T", "name": "三菱UFJフィナンシャルG", "category": "メガバンク首位・金利上昇恩恵", "thesis": "日銀利上げによる純利息収入拡大と潤沢な株主還元余力"},
            {"symbol": "8316.T", "name": "三井住友フィナンシャルG", "category": "メガバンク・高収益性", "thesis": "Olive経済圏の拡大と高い自己資本利益率。増配継続"},
            {"symbol": "8411.T", "name": "みずほフィナンシャルG", "category": "メガバンク・大企業取引強み", "thesis": "国内金利引き上げの最大感応度と積極的な自社株買い方針"},
            {"symbol": "2914.T", "name": "日本たばこ産業 (JT)", "category": "高配当・世界的キャッシュフロー", "thesis": "配当利回り約5%。世界規模の価格決定力と圧倒的FCF"},
            {"symbol": "7203.T", "name": "トヨタ自動車", "category": "グローバル自動車首位", "thesis": "ハイブリッド戦略の大成功とPBR1倍超えに向けたグループ再編"},
            {"symbol": "4063.T", "name": "信越化学工業", "category": "半導体シリコンウエハ世界首位", "thesis": "無借金・自己資本比率80%超の要塞バランスシート。塩ビ・ウエハ独占"},
            {"symbol": "6861.T", "name": "キーエンス", "category": "ファクトリーオートメーションセンサ首位", "thesis": "営業利益率50%超。バフェットMoatの最高峰・超高収益モデル"},
            {"symbol": "7974.T", "name": "任天堂", "category": "世界的IPエンターテインメント", "thesis": "マリオ・ポケモン等の不滅のIP価値と巨額キャッシュポジション"},
            {"symbol": "AAPL", "name": "Apple", "category": "エコシステム・自社株買い王", "thesis": "バフェット最大主力。iOS経済圏の堀と年間10兆円規模の自社株買い"},
            {"symbol": "KO", "name": "Coca-Cola", "category": "生活必需品・60年連続増配", "thesis": "世界的ブランド認知度とインフレ価格転嫁力。景気後退耐性"},
            {"symbol": "JPM", "name": "JPMorgan Chase", "category": "米国最強メガバンク", "thesis": "ダイモンCEO率いる圧倒的規模と業界屈指の資本効率"},
            {"symbol": "BRK-B", "name": "Berkshire Hathaway", "category": "投資の神様・複合企業体", "thesis": "バフェット率いる要塞コングロマリット。手元現金40兆円の安全域"},
            {"symbol": "JNJ", "name": "Johnson & Johnson", "category": "ヘルスケア・62年連続増配", "thesis": "医薬品・医療機器のディフェンシブ性。AAA格付けの財務"}
        ],
        "DEEP_VALUE": [
            {"symbol": "5401.T", "name": "日本製鉄", "category": "高付加価値鋼・PBR改革", "thesis": "東証PBR1倍割れ改善の主役。海外高級鋼シフトと高配当利回り"},
            {"symbol": "7267.T", "name": "本田技研工業 (ホンダ)", "category": "自動車・二輪世界首位", "thesis": "二輪の高収益基盤と割安なPBR（0.6倍近辺）。自社株買い積極化"},
            {"symbol": "1812.T", "name": "鹿島建設", "category": "建設・再開発・半導体工場", "thesis": "TSMC熊本工場等の大型案件受注残豊富。PBR改善方針公表"},
            {"symbol": "1801.T", "name": "大成建設", "category": "スーパーゼネコン・インフラ再構築", "thesis": "資材高転嫁の進展と採算性重視への回帰。割安バリュー水準"},
            {"symbol": "5020.T", "name": "ENEOSホールディングス", "category": "石油元売り首位・EV素材", "thesis": "製油所集約による収益性改善と低PBR是正・積極配当還元"},
            {"symbol": "9101.T", "name": "日本郵船", "category": "海運大手・高配当還元", "thesis": "地政学リスクによる運賃高止まりと豊富な余剰資金の還元"},
            {"symbol": "INTC", "name": "Intel", "category": "半導体ファウンドリ再建", "thesis": "株価歴史的低迷による解散価値接近。米政府補助金と再建期待"},
            {"symbol": "F", "name": "Ford Motor", "category": "伝統的自動車・高配当", "thesis": "配当利回り5%超。商用車Pro部門の安定キャッシュフロー"},
            {"symbol": "GM", "name": "General Motors", "category": "自動車・大規模自社株買い", "thesis": "驚異的な自社株買い推進でEPS急拡大。PER5倍近辺の超割安放置"},
            {"symbol": "VALE", "name": "Vale", "category": "鉄鉱石・ニッケル世界首位級", "thesis": "低生産コストと高配当。世界的なEV用ニッケル需要"}
        ],
        "EUROPE_GLOBAL": [
            {"symbol": "ASML", "name": "ASML Holding (蘭・半導体EUV露光)", "category": "EUV半導体露光装置・世界独占", "thesis": "先端AI半導体（2nm/3nm）製造に不可欠な極端紫外線（EUV）露光装置を世界で唯一製造。鉄壁の独占ワイド・モート（米国ADR/USD建て）"},
            {"symbol": "SAP", "name": "SAP SE (独・エンタープライズERP)", "category": "欧州テック首位・クラウドERP", "thesis": "世界トップ企業の基幹システムを牛耳るERP絶対王者。クラウド移行加速とBusiness AI統合で高成長・高営業利益率（米国ADR/USD建て）"},
            {"symbol": "NVO", "name": "Novo Nordisk (丁・バイオ製薬)", "category": "GLP-1肥満症薬・糖尿病薬首位", "thesis": "画期的抗肥満薬Wegovy/Ozempicで世界を席巻。欧州時価総額トップクラスを誇る超高収益バイオメガファーマ（米国ADR/USD建て）"},
            {"symbol": "AZN", "name": "AstraZeneca (英・バイオ製薬)", "category": "オンコロジー抗がん剤・メガファーマ", "thesis": "抗がん剤エンハーツ等の大型ブロックバスター薬が絶好調。強固なパイプラインと安定した増配トラックレコード（米国ADR/USD建て）"},
            {"symbol": "LVMUY", "name": "LVMH (仏・高級品コングロマリット)", "category": "ルイヴィトン・ディオール・世界的IP", "thesis": "圧倒的なブランド価格決定力と富裕層マーケットの掌握。インフレ耐性と長期的なフリーキャッシュフロー創出力（米国ADR/USD建て）"},
            {"symbol": "EADSY", "name": "Airbus (仏・航空機世界首位)", "category": "民間航空機・防衛・宇宙", "thesis": "ボーイングの失速に伴い単通路機A320neoシリーズで市場シェア首位を独占。過去最大の受注残高を抱える航空宇宙巨人（米国ADR/USD建て）"}
        ]
    }

    EUROPE_SYMBOLS = {"ASML", "SAP", "NVO", "AZN", "LVMUY", "EADSY"}

    @classmethod
    def _watchlist_file_path(cls) -> str:
        base_dir = os.getenv('APPDATA') or os.path.expanduser('~/.local/share')
        app_data_dir = os.path.join(base_dir, 'LuminaAI')
        os.makedirs(app_data_dir, exist_ok=True)
        return os.path.join(app_data_dir, 'hedge_fund_custom_watchlist.json')

    @classmethod
    def get_custom_watchlist(cls) -> List[Dict[str, Any]]:
        """Load user-defined custom watchlisted tickers"""
        try:
            p = cls._watchlist_file_path()
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    @classmethod
    def cleanup_expired_custom_watchlist(
        cls, 
        held_symbols: Optional[Any] = None, 
        max_age_days: int = 30, 
        max_capacity: int = 15
    ) -> List[Dict[str, Any]]:
        """
        自律クリーンアップ・卒業エンジン:
        1. 30日賞味期限: 登録日時から30日以上経過した未保有銘柄を自動卒業
        2. 最大定員管理: 上限枠（15銘柄）を超過した場合、古い未保有銘柄から順に自動押し出し
        ※現在保有中のポジション銘柄は絶対に除外されません。
        """
        held = set(held_symbols) if held_symbols else set()
        items = cls.get_custom_watchlist()
        if not items:
            return []

        from datetime import datetime, timedelta
        now = datetime.now()
        cutoff_date = now - timedelta(days=max_age_days)

        graduated = []
        survivors = []

        for item in items:
            sym = item.get("symbol", "")
            # 保有中の銘柄は絶対に除外しない
            if sym in held:
                survivors.append(item)
                continue

            added_at_str = item.get("added_at")
            is_expired = False
            if added_at_str:
                try:
                    dt = datetime.strptime(added_at_str, "%Y-%m-%d %H:%M:%S")
                    if dt < cutoff_date:
                        is_expired = True
                except Exception:
                    pass

            if is_expired:
                item_copy = dict(item)
                item_copy["graduation_reason"] = f"登録から{max_age_days}日経過（材料賞味期限満了）"
                graduated.append(item_copy)
            else:
                survivors.append(item)

        # 定員枠チェック（最大15銘柄）：超過分は古い未保有銘柄から卒業
        if len(survivors) > max_capacity:
            held_items = [it for it in survivors if it.get("symbol") in held]
            unheld_items = [it for it in survivors if it.get("symbol") not in held]

            # unheld_items を新しい順にソート（added_at DESC）
            unheld_items.sort(key=lambda x: x.get("added_at", ""), reverse=True)

            allowed_unheld = max(0, max_capacity - len(held_items))
            kept_unheld = unheld_items[:allowed_unheld]
            overflow_unheld = unheld_items[allowed_unheld:]

            for ov in overflow_unheld:
                ov_copy = dict(ov)
                ov_copy["graduation_reason"] = f"監視枠上限（{max_capacity}銘柄）超過による新陳代謝"
                graduated.append(ov_copy)

            survivors = held_items + kept_unheld

        if graduated:
            try:
                with open(cls._watchlist_file_path(), 'w', encoding='utf-8') as f:
                    json.dump(survivors, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[MarketScreener] cleanup save error: {e}")

        return graduated

    @classmethod
    def add_custom_ticker(cls, symbol: str, name: str = "", category: str = "マイ監視銘柄", thesis: str = "ユーザー独自登録の巡回銘柄") -> Dict[str, Any]:
        """Add ticker to user custom watchlist (with 15-ticker max capacity auto-pruning)"""
        sym = MarketDataFeed.normalize_symbol(symbol.strip().upper())
        items = cls.get_custom_watchlist()
        if any(x["symbol"] == sym for x in items):
            return {"success": False, "message": f"銘柄 {sym} は既に監視リストに存在します"}

        # 枠数上限（15銘柄）を超過する場合、事前に最古の未保有株を1件押し出し
        if len(items) >= 15:
            cls.cleanup_expired_custom_watchlist(max_capacity=14)
            items = cls.get_custom_watchlist()
        
        # Auto-fetch company name from market feed
        if not name or name == sym:
            try:
                data = MarketDataFeed.get_stock_data(sym)
                name = data.get("company_name") or sym
            except Exception:
                name = sym

        new_item = {
            "symbol": sym,
            "name": name,
            "category": category,
            "thesis": thesis,
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        items.append(new_item)
        try:
            with open(cls._watchlist_file_path(), 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            return {"success": True, "item": new_item, "message": f"「{name} ({sym})」を巡回監視リストに追加しました！"}
        except Exception as e:
            return {"success": False, "message": f"保存エラー: {e}"}

    @classmethod
    def auto_discover_catalyst_stocks(cls, market: str = "ALL") -> List[Dict[str, Any]]:
        """
        Scan breaking market news via NewsFeed and automatically add discovered
        high-conviction catalyst stocks to the custom watchlist.
        """
        discovered = NewsFeed.discover_catalyst_stocks_with_ai()
        if not discovered:
            return []

        # 事前に定員・賞味期限クリーンアップを実行
        cls.cleanup_expired_custom_watchlist(max_capacity=15)

        # Get all existing symbols across standard universe and custom watchlist
        existing_symbols = set()
        for cat_list in cls.UNIVERSE.values():
            for s in cat_list:
                existing_symbols.add(s["symbol"])
        for c in cls.get_custom_watchlist():
            existing_symbols.add(c["symbol"])

        added_items = []
        for d in discovered:
            raw_sym = d.get("symbol", "").strip().upper()
            if not raw_sym:
                continue
            norm_sym = MarketDataFeed.normalize_symbol(raw_sym)
            if norm_sym in existing_symbols:
                continue  # Already in universe or watchlist

            name = d.get("name") or norm_sym
            cat = f"AI速報発掘: {d.get('category', '好材料株')}"
            thesis = f"【材料速報検知 (確信度{d.get('conviction_score', 80)}点)】{d.get('catalyst', '好材料発表')}"

            res = cls.add_custom_ticker(norm_sym, name=name, category=cat, thesis=thesis)
            if res.get("success"):
                added_items.append(res.get("item"))
                existing_symbols.add(norm_sym)

        return added_items

    @classmethod
    def remove_custom_ticker(cls, symbol: str) -> bool:
        """Remove ticker from custom watchlist"""
        sym = MarketDataFeed.normalize_symbol(symbol.strip().upper())
        items = cls.get_custom_watchlist()
        new_items = [x for x in items if x["symbol"] != sym]
        if len(new_items) != len(items):
            try:
                with open(cls._watchlist_file_path(), 'w', encoding='utf-8') as f:
                    json.dump(new_items, f, ensure_ascii=False, indent=2)
                return True
            except Exception:
                pass
        return False

    @classmethod
    def scan_opportunities(
        cls, 
        category: str = "ALL", 
        max_results: int = 6, 
        include_europe: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Scan and rank top investment opportunities across the expanded 65+ universe and custom watchlist.
        Evaluates ALL candidates in parallel (0 LLM tokens, pure quant calculation).
        Supports include_europe for adaptive asset allocation (switches off at >= 2M JPY).
        """
        candidates = []
        custom_list = cls.get_custom_watchlist()
        if category == "ALL":
            candidates.extend(custom_list)
            universe_keys = ["DEFENSE_ENERGY", "AI_GROWTH", "VALUE_DIVIDEND", "DEEP_VALUE"]
            if include_europe:
                universe_keys.append("EUROPE_GLOBAL")
            for cat_key in universe_keys:
                candidates.extend(cls.UNIVERSE.get(cat_key, []))
        elif category in cls.UNIVERSE:
            candidates.extend(cls.UNIVERSE[category])
        else:
            candidates.extend(cls.UNIVERSE["VALUE_DIVIDEND"])

        # Filter out European ADRs if Europe inclusion is disabled (JP-US concentration mode)
        if not include_europe:
            candidates = [c for c in candidates if c["symbol"] not in cls.EUROPE_SYMBOLS]

        # Deduplicate candidates by symbol
        seen = set()
        unique_candidates = []
        for c in candidates:
            sym_key = c["symbol"]
            if sym_key not in seen:
                seen.add(sym_key)
                unique_candidates.append(c)

        # Worker for fast parallel scoring (0 tokens)
        def _score_worker(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            sym = item["symbol"]
            try:
                data = MarketDataFeed.get_stock_data(sym)
                price = data.get("current_price") or 0.0
                curr = data.get("currency", "JPY" if sym.endswith(".T") else "USD")
                pe = data.get("pe_trailing")
                pb = data.get("pb_ratio")
                div = data.get("dividend_yield", 0.0)
                roe = data.get("roe")
                ret20 = data.get("history_metrics", {}).get("return_20d_pct", 0.0)

                # Composite Quant Score Calculation (Base: 72)
                score = 72
                # Custom watchlist bonus
                if any(x["symbol"] == sym for x in custom_list):
                    score += 6

                cat = item.get("category", "")
                strat = category

                # Strategy-specific evaluation
                if strat in ["EUROPE_GLOBAL", "ALL"] or "EUV" in cat or "ERP" in cat or "製薬" in cat:
                    if roe and roe >= 12.0: score += 10
                    if ret20 and ret20 > 3.0: score += 6

                if strat in ["VALUE_DIVIDEND", "ALL"] or "商社" in cat or "配当" in cat:
                    if div and div >= 3.0: score += 10
                    if roe and roe >= 10.0: score += 8
                    if pb and pb <= 1.5: score += 5
                
                if strat in ["AI_GROWTH", "ALL"] or "半導体" in cat or "AI" in cat:
                    if ret20 and ret20 > 5.0: score += 10
                    if data.get("revenue_growth") and data.get("revenue_growth") > 15: score += 10

                if strat in ["DEFENSE_ENERGY", "ALL"] or "重工" in cat or "防衛" in cat or "電力" in cat:
                    if ret20 and ret20 > 8.0: score += 12
                    if roe and roe >= 9.0: score += 6

                if strat in ["DEEP_VALUE", "ALL"]:
                    if pb and pb <= 1.0: score += 14
                sma200 = data.get("history_metrics", {}).get("sma_200")
                is_stage2 = (price >= (sma200 * 0.98)) if (sma200 and price > 0) else True
                if is_stage2:
                    score += 4  # Stage 2 Uptrend Bonus
                else:
                    score -= 15 # Stage 4 Downtrend Falling Knife Penalty

                # SEC Form 4 Insider Catalyst (US stocks):
                # When stock is in Stage 2 uptrend, cluster insider buying provides +5 catalyst bonus
                insider_metrics = SecInsiderFeed.get_insider_metrics(sym)
                insider_boost = insider_metrics.get("score_boost", 0)
                if is_stage2 and insider_boost > 0:
                    score += insider_boost

                score = min(99, max(50, score))

                item_thesis = item["thesis"]
                if insider_metrics.get("signal") == "STRONG_INSIDER_BUYING":
                    item_thesis = f"【SEC Form 4 役員自社株買い検知】{item_thesis}"

                recent_closes = MarketDataFeed.get_historical_closes(sym, period="1mo")

                return {
                    "symbol": sym,
                    "name": item["name"],
                    "category": item["category"],
                    "thesis": item_thesis,
                    "current_price": price,
                    "currency": curr,
                    "pe": pe,
                    "pb": pb,
                    "dividend_yield": div,
                    "roe": roe,
                    "return_20d_pct": ret20,
                    "sma_200": sma200,
                    "is_stage2": is_stage2,
                    "insider_metrics": insider_metrics,
                    "ai_score": score,
                    "recent_closes": recent_closes
                }
            except Exception:
                return None

        # Execute parallel evaluation (ThreadPoolExecutor)
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {executor.submit(_score_worker, it): it for it in unique_candidates}
            for fut in as_completed(future_map):
                res = fut.result()
                if res and res.get("current_price", 0) > 0:
                    results.append(res)

        # Sort descending by composite AI score
        results.sort(key=lambda x: x["ai_score"], reverse=True)
        final_top = results[:max_results]
        try:
            cls.save_screener_cache(category, final_top)
        except Exception:
            pass
        return final_top

    @classmethod
    def get_ai_market_hot_brief(cls) -> Dict[str, Any]:
        """
        Generate real-time AI market summary highlighting macro tailwinds and hot sectors.
        """
        try:
            from core.state_manager import load_app_settings
            cfg = load_app_settings()
            api_key = cfg.get("google_api_key", "")
            if not api_key:
                return cls._default_brief()

            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            prompt = """現在の日本株・米国株市場において、AIヘッジファンドが注目すべき「今週のホットテーマ3選」と「買い推奨セクター」を簡潔にまとめてください。
以下のJSONフォーマットのみを出力してください:
{
  "market_mood": "強気 (Bullish) / 押し目買い好機",
  "hot_themes": [
    {"theme": "防衛・重工＆先端AI電力インフラ", "reason": "地政学安全保障予算の倍増とデータセンター電線・超多心光コネクタの特需爆発"},
    {"theme": "東証PBR1倍割れ改善＆5大総合商社", "reason": "バフェット買い増し継続と過去最高の自社株買い・増配の波"},
    {"theme": "メガテックAIマネタイズ＆米利下げサイクル", "reason": "金利低下によるバリュエーション支援とエンタープライズAI需要"}
  ],
  "lead_advice": "指数高値圏では一括投資を避け、堀の深い高配当株・防衛重工と急成長AIインフラ銘柄への時間分散（打診買い）が推奨されます。"
}
"""
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.5
            )
            for model_name in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-3.8-flash"]:
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    )
                    if res and res.text:
                        raw = res.text.strip()
                        if raw.startswith("```json"): raw = raw[7:]
                        if raw.endswith("```"): raw = raw[:-3]
                        return json.loads(raw.strip())
                except Exception as m_err:
                    print(f"[MarketScreener] {model_name} error: {m_err}")
            return cls._default_brief()
        except Exception as e:
            print(f"[MarketScreener] Hot brief error: {e}")
            return cls._default_brief()

    @classmethod
    def _default_brief(cls) -> Dict[str, Any]:
        return {
            "market_mood": "強気 (Bullish) / 押し目買い好機",
            "hot_themes": [
                {"theme": "防衛・重工＆先端AI電力インフラ", "reason": "地政学安全保障予算の倍増とデータセンター電線・超多心光コネクタの特需爆発"},
                {"theme": "東証PBR改革・5大総合商社", "reason": "バフェット買い増し継続と過去最高の自社株買い・増配の波"},
                {"theme": "メガテックAIマネタイズ＆米利下げ", "reason": "金利低下によるバリュエーション支援とエンタープライズAI需要"}
            ],
            "lead_advice": "感情的な高値掴みを避け、ウォーレン・バフェット流の「強固な堀」とキャシー・ウッド流の「AIイノベーション」を組み合わせた分散配置が最高のリワードレシオをもたらします。"
        }

    @classmethod
    def _cache_file_path(cls) -> str:
        base_dir = os.getenv('APPDATA') or os.path.expanduser('~/.local/share')
        app_data_dir = os.path.join(base_dir, 'LuminaAI')
        os.makedirs(app_data_dir, exist_ok=True)
        return os.path.join(app_data_dir, 'hedge_fund_screener_cache.json')

    @classmethod
    def get_cached_opportunities(cls, category: str = "ALL", max_age_seconds: int = 43200) -> Optional[List[Dict[str, Any]]]:
        """
        Load cached screener results from disk without blocking the main UI (TTL: 12 hours).
        """
        try:
            p = cls._cache_file_path()
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                cached_at = data.get("cached_at", 0)
                if time.time() - cached_at < max_age_seconds:
                    cats = data.get("categories", {})
                    if category in cats and cats[category]:
                        return cats[category]
                    if "ALL" in cats and cats["ALL"]:
                        return cats["ALL"]
        except Exception as e:
            print(f"[MarketScreener] Cache load error: {e}")
        return None

    @classmethod
    def get_cached_market_brief(cls, max_age_seconds: int = 43200) -> Dict[str, Any]:
        """
        Load cached AI market brief from disk without LLM delay (TTL: 12 hours).
        """
        try:
            p = cls._cache_file_path()
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                cached_at = data.get("cached_at", 0)
                if time.time() - cached_at < max_age_seconds:
                    if "brief" in data and data["brief"]:
                        return data["brief"]
        except Exception:
            pass
        return cls._default_brief()

    @classmethod
    def save_screener_cache(cls, category: str, results: List[Dict[str, Any]], brief: Optional[Dict[str, Any]] = None):
        """
        Save screener results and market brief to disk cache.
        """
        try:
            p = cls._cache_file_path()
            data = {}
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data["cached_at"] = time.time()
            if "categories" not in data:
                data["categories"] = {}
            if results:
                data["categories"][category] = results
            if brief:
                data["brief"] = brief
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[MarketScreener] Cache save error: {e}")

    @classmethod
    def get_instant_preset_opportunities(cls, category: str = "ALL") -> List[Dict[str, Any]]:
        """
        Curated immediate top opportunities for 0ms instantaneous display on fresh launch.
        Completely eliminates UI freeze upon entering the Hedge Fund screen.
        """
        presets = [
            {
                "symbol": "7011.T",
                "name": "三菱重工業",
                "category": "防衛首位・航空宇宙・ガスタービン",
                "thesis": "防衛予算倍増と次世代原発・脱炭素タービンの世界的需要。モメンタム最強銘柄",
                "current_price": 2420.0,
                "currency": "JPY",
                "pe": 26.4,
                "pb": 2.3,
                "dividend_yield": 1.2,
                "roe": 12.8,
                "return_20d_pct": 8.4,
                "is_stage2": True,
                "ai_score": 96,
                "recent_closes": [2150.0, 2180.0, 2190.0, 2220.0, 2210.0, 2240.0, 2270.0, 2300.0, 2290.0, 2310.0, 2330.0, 2350.0, 2380.0, 2400.0, 2420.0]
            },
            {
                "symbol": "5803.T",
                "name": "フジクラ",
                "category": "AIデータセンター電線・光ファイバー",
                "thesis": "生成AI向け超多心光コネクタで世界独占的シェア。株価爆発的急騰トレンド",
                "current_price": 5890.0,
                "currency": "JPY",
                "pe": 22.1,
                "pb": 3.1,
                "dividend_yield": 1.6,
                "roe": 18.2,
                "return_20d_pct": 14.2,
                "is_stage2": True,
                "ai_score": 95,
                "recent_closes": [4900.0, 5020.0, 5100.0, 5180.0, 5250.0, 5320.0, 5400.0, 5480.0, 5550.0, 5600.0, 5710.0, 5780.0, 5840.0, 5890.0]
            },
            {
                "symbol": "NVDA",
                "name": "NVIDIA",
                "category": "生成AI半導体・GPU絶対王者",
                "thesis": "データセンター向けAIインフラの9割を独占。Blackwell需要爆発",
                "current_price": 138.5,
                "currency": "USD",
                "pe": 45.2,
                "pb": 28.5,
                "dividend_yield": 0.05,
                "roe": 115.0,
                "return_20d_pct": 11.5,
                "is_stage2": True,
                "ai_score": 94,
                "recent_closes": [121.0, 122.5, 124.0, 126.0, 125.5, 128.0, 130.0, 131.5, 133.0, 135.0, 136.2, 137.0, 138.5]
            },
            {
                "symbol": "8058.T",
                "name": "三菱商事",
                "category": "総合商社首位・累進配当",
                "thesis": "バフェット保有銘柄。強固な資源・非資源CFと積極的自社株買い",
                "current_price": 2780.0,
                "currency": "JPY",
                "pe": 10.8,
                "pb": 1.1,
                "dividend_yield": 3.6,
                "roe": 14.5,
                "return_20d_pct": 4.1,
                "is_stage2": True,
                "ai_score": 92,
                "recent_closes": [2680.0, 2690.0, 2710.0, 2720.0, 2700.0, 2730.0, 2740.0, 2750.0, 2760.0, 2770.0, 2780.0]
            },
            {
                "symbol": "PLTR",
                "name": "Palantir Technologies",
                "category": "企業・防衛向けAIプラットフォーム",
                "thesis": "AIP（エンタープライズAI）の導入加速。S&P500採用で機関マネー流入",
                "current_price": 43.8,
                "currency": "USD",
                "pe": 82.0,
                "pb": 16.2,
                "dividend_yield": 0.0,
                "roe": 22.4,
                "return_20d_pct": 16.8,
                "is_stage2": True,
                "ai_score": 91,
                "recent_closes": [36.0, 37.2, 38.5, 39.0, 40.1, 40.8, 41.5, 42.0, 42.9, 43.8]
            },
            {
                "symbol": "6301.T",
                "name": "コマツ",
                "category": "建機世界2位・資源インフラ",
                "thesis": "IoT建機Komtraxによる高収益フリート。鉱山向け資源需要と安定増配",
                "current_price": 4150.0,
                "currency": "JPY",
                "pe": 9.8,
                "pb": 1.25,
                "dividend_yield": 4.1,
                "roe": 13.9,
                "return_20d_pct": 3.2,
                "is_stage2": True,
                "ai_score": 89,
                "recent_closes": [4020.0, 4040.0, 4060.0, 4050.0, 4080.0, 4100.0, 4110.0, 4130.0, 4150.0]
            }
        ]
        return presets
