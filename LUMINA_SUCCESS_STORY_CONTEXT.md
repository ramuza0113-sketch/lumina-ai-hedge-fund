# Lumina Capital Success Story & Technical Context Data
## 【ブログ・記事自動生成用 プロンプトインプット資料】

本書は、自律型AIヘッジファンドエンジン『Lumina Capital (v6.0)』のオープンソース公開から、海外コミュニティ（Reddit）での熱狂、そして世界最大のクアント投資リソース集『awesome-quant（⭐️ 15,000+）』への正式マージまでの全事実・技術背景・ログデータをまとめた生成用コンテキスト資料です。

---

## 1. プロジェクト基本情報
- **プロダクト名**: Lumina Capital (AI Hedge Fund Engine v6.0)
- **開発者**: prompter_note (@ramuza0113-sketch / @prompter_note)
- **GitHubリポジトリ**: https://github.com/ramuza0113-sketch/lumina-ai-hedge-fund
- **ライセンス**: Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
- **公式技術ブログ**: https://prompter-note.com
- **Qiita解説記事**: https://qiita.com/ramuza0113/items/434af1b23fa220590f017 (公開数日で460+ Views)
- **初期トラフィック実績**: 公開数日でユニーククローン数84人、総クローン数157回突破

---

## 2. 開発背景とコア思想：「Models reason, software calculates」
### 既存の「LLM投資bot（PoC）」が抱える3大欠陥
1. **推論と計算の混同**:
   ChatGPTやClaudeに「テクニカル指標の数値を計算させ、直接買い/売りを判断させる」アプローチは、数値計算のハルシネーション（誤差・幻覚）を招き、致命的な誤発注を引き起こす。
2. **市場摩擦（Friction）の完全無視**:
   オープンソースの多くのbotは、手数料（往復0.05%〜）や板スプレッドによる不利約定（スリッページ）を考慮しておらず、バックテストで勝てても実戦で即死する。
3. **急落時の防衛機構（セーフティネット）の欠如**:
   LLMが長文で推論・議論している15〜30秒の間に相場が急変した場合、損切りが間に合わずポートフォリオが破綻する。

### Lumina Capitalの工学的解決策
- **原則**: 「モデルは推論し、ソフトウェアが計算する」
- **決定論的数理クオンツ層**:
  Microsoft Qlib の「Alpha158」全158ファクターを純粋なPython（numpy / pandas）で完全ベクトル化実装。LLMのハルシネーションが介在する余地をゼロに排除。
  さらにLightGBMメタ決定木による勝率判定フィルターを前段に配置。
- **時系列基底AI予測**:
  Google TimesFM による5日先確率ファンチャート（50%, 80%, 90%信頼区間）の算出。
- **デュアルスピード・アーキテクチャ**:
  15分サイクルの「LLM深層合議ループ」と、完全に独立した10秒周期の「高速番犬センチネルスレッド」を並行稼働。急落時はLLMのAPI応答を待たずに動的ATRストップロスを物理執行。
- **反迎合（Anti-Sycophancy）マルチエージェント合議 (LangGraph)**:
  ウォーレン・バフェット、ジョージ・ソロス、マイケル・バーリ、キャシー・ウッド、ベンジャミン・グレアム、ウィリアム・オニール、CISの7人の伝説的投資家ペルソナが、互いの意見を見ずに独立並列で分析。
  その後、最強の強気派と最強の弱気派がファクトベースで一騎打ちのクロスディベートを展開。
  さらに最高リスク責任者（CRO）が、テールリスクや粉飾決算兆候を検知した場合に「0%配分（絶対拒否権）」を強制執行。
- **3D因果ナレッジグラフ & GraphRAG (Neo4j & Graphiti)**:
  トレードの反省記憶（Reflexion）やSEC 10-Kサプライチェーン関係性をNeo4j 3D WebGLグラフに蓄積。TSMC → NVIDIAのような川上ボトルネックのリスク伝播を多段ホップで追跡。

---

## 3. 世界水準のオープンソースリポジトリ設計
海外の一流エンジニア・メンテナーを迎えるにあたり、以下の品質基準を完全達成：
- **GitHub Community Standards 100%（オールグリーン達成）**:
  - `CODE_OF_CONDUCT.md`（Contributor Covenant v2.1準拠）
  - `CONTRIBUTING.md`（数理ファクター追加や合議開発の参加ガイド）
  - `SECURITY.md`（APIキー漏洩防止・脆弱性非公開報告窓口）
  - バグ報告・機能要望のGitHub IssueテンプレートおよびPull Requestテンプレート
  - `ACCESSIBILITY.md`（WCAG 2.1 AA準拠、高コントラスト設計）
  - `CITATION.cff`（世界の大学・研究機関が論文や研究ブログで公式引用できる学術引用ファイル）
- **GitHub Actions 自動CIパイプライン**:
  - プッシュ・PRごとにPython 3.10 / 3.11 環境で構文検証とflake8コード整合性検査が自動稼働。
  - README最上部に誇らしく輝く `CI: passing（緑色バッジ）`。
- **敷居ゼロの親切設計**:
  - Google AI Studioで無料発行できる `GEMINI_API_KEY` 1本で全7エージェントがフル稼働（高額なOpenAI有料キー不要）。
  - 高価なGPUサーバー不要。Mac（Apple Silicon M1〜M4）、Windows、Linuxの普通のCPUで軽快動作。
  - Xやnoteへの自動投稿機能はデフォルトで完全な「ローカルプレビュー／下書きモード」（外部へ勝手に送信されない安全性）。
  - Neo4jは完全オプショナル（未起動でも内蔵SQLiteで100%全機能が動作。試したい人のみDockerコマンド1行で即接続）。

---

## 4. 海外コミュニティ（Reddit）での熱狂と反響
世界最大のPythonコミュニティ **`r/Python`（登録者110万人以上）** にて、「決定論的ファクター数理とLLM推論の完全分離」をテーマにディスカッションを投稿：
- **わずか30分で 1,400 Views（1.4K表示）を記録**。
- 海外エンジニア（`PrincipleResident372` 氏）からの熱烈なコメント：
  > *"This reminds me of a project where someone tried to make a bot do all the math inside the prompt itself, it went about as well as you'd expect. The split you got here makes lot more sense. let the code crunch numbers and keep the LLM for the fluffy strategy debates... I'd look at the repo if you drop the link. been wanting to see a cleaner way to mix Qlib factors with agent based deliberation."*  
  > （「プロンプト内で全部計算させようとして大惨事になった某botを思い出したよ（笑）。あなたのこの『コードが数値をガリガリ計算し、LLMは戦略議論に専念させる』という分離は圧倒的に理に適っている。ぜひリポジトリのリンクを教えてくれ！見に行きたい！」）
- CRO（リスク最高責任者）の拒否権や、キャシー・ウッドAIの買い向かい癖をバフェットやバーリが論破する仕組みについて海外開発者と熱い技術ディスカッションを展開。

---

## 5. 世界最大のクアントリソース集『awesome-quant（⭐️15,000+）』正式採択・マージの全記録
### awesome-quant とは
Wilson Freitas 氏が主宰する、GitHub上で世界一有名なクアント投資・金融工学オープンソースリポジトリ（Stars 15,000件超え）。世界中のヘッジファンド関係者、アルゴリズムトレーダー、金融データサイエンティストが必ず参照するバイブル。

### マージまでのドラマ
1. **厳格な審査**:
   PR提出後、URLの生存確認、アルファベット順ソート、重複排除、マークダウン書式の厳格な自動テスト（Validate PR）をわずか12秒で完全クリア。
2. **コンフリクト発生とオーナーの神対応**:
   他PRのマージによりREADMEで競合（コンフリクト）が発生した際、オーナーの Wilson Freitas 氏本人が直々に登場：
   > *"The README merge conflict has been resolved locally, preserving the entries already on main and this PR's reviewed contribution. The resolved additions pass the repository's strict format, URL and duplicate checks."*  
   > （「手元で競合を綺麗に解消したよ。追加内容はうちの厳格なフォーマット・URL・重複チェックをすべて合格しているよ。」）
3. **GitHub APIのレートリミット（403）を乗り越えて**:
   Actions実行時にGitHub API制限に引っかかった際も、Wilson 氏はクールダウン時間（13:42 UTC）を正確に特定し、自らコミットをプッシュ。
4. **正式マージ（🟣 Merged）完了**:
   Trading & Backtesting 部門に、世界の一流クアントツール（Backtrader, Zipline, Qlib等）と並んで『Lumina Capital』が公式に永久掲載される。

