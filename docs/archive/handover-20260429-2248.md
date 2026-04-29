## Session Handover

**最終更新:** 2026-04-29 18:50

---

## 前提と目的 (Context & Intent)

前セッション（輝度ゲート + F-13 救済 UI 実装）の **次の最優先タスク**だった
**実機 2 ページ統合テスト**を再挑戦するセッション。今回の検証ターゲット：

1. 輝度ゲートが暗所ハルシネーションを撮影前に弾くか
2. F-13 救済フロー（merge-save → uncertain_boundaries 検出 → Read で画像確認 → apply-boundary-fix）が実用ベースで回るか
3. Pro 二次 OCR の品質差を改めて 1 セッション通しで観察

撮影元 PC のモニターを変更し（前回と同じ Zenn 記事「GitHubで人生を管理する」、4-5 ページ想定）、4 ページ実走した。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### コミット

このセッションでは **コードもドキュメントも未コミット** — テストで検出された 3 件の改善ポイントは次セッションで実装＋コミットする。

### 検証結果（実機 4 ページ走行）

| 項目 | 結果 |
|------|------|
| 撮影 4 ページ | `/tmp/screen-read-20260429-165120/page-{1..4}.jpg` |
| 輝度ゲート | 4 枚すべて通過（mean 113-119, std 70-74, dark_ratio 0.16-0.22） |
| ブレ検知 | 全枚 variance 613-809（閾値 100 を大幅クリア） |
| 一次 OCR (Flash) page-1 | 重大な誤字: `Issues` → `Zenes`, `life` → `1ste`, `axross` → `ぁ`, 末尾の数行が完全に再構成（「機能的に〜」が脱落、「に当てはめずに」と化ける） |
| 二次 OCR (Pro) page-1 〜 page-4 | 固有名詞・記号・コードフェンスがほぼ完璧。$0.05/page。Flash の構造的誤読を直す |
| same-page 終了判定 | page-2 vs page-3: 60.3、page-3 vs page-4: 74.6（ともに `is_same: false`、終了判定発動せず） |
| merge-save 1 回目 | クラッシュ（`page-*.ocr.json` glob 衝突。後述） |
| merge-save 2 回目 | 成功。`uncertain_boundaries: 1`（境界 0: page1↔page2） |
| F-13 救済 (C 案) | `apply-boundary-fix --replacement -` で空文字 → マーカー除去のみ → `remaining_uncertain: 0` |
| 最終出力 | `/home/slmbrcat/obsidian-vault/00_Inbox/clip-20260429-1743.md`（page1↔page2 領域に重複が残るが、後段は kk=9/k=17 で正常結合） |

### 検出された 3 件の問題

1. **`_list_page_files` glob が OCR 中間ファイルとぶつかる**（`screen_read_helper.py:132`）
   - `session_dir.glob("page-*.json")` が `page-1.ocr.json` を拾い、`p.stem.split("-")[1]` が `2.ocr` で ValueError
   - **修正案:** `page-[0-9][0-9][0-9].json` のように 3 桁数字限定パターンへ。あるいは `_ocr_raw/` サブディレクトリ運用を SKILL.md に明文化
   - 今回の現場対応: OCR JSON を `_ocr_raw/` に手で退避してリトライ

2. **page-N が page-(N-1) を完全包含するケースで overlap 検出が破綻**
   - 今回 page-2 (Pro) は「という記事があります」（記事中盤）から始まり、page-1 末尾「だって仕事でずっと使ってるんだもん」を**含んだ上でさらに先まで**読んでいた
   - merge.py は「prev 末尾 K 行 ↔ next 先頭 K 行」マッチを探すので、prev 全体が next の先頭ブロック内に潜んでいる場合は overlap が検出できない
   - **撮影オペレーション側の対策:** Up キー戻し量を控えめにして「next 先頭 K 行が prev 末尾 K 行と直接重なる」状態を維持する。SKILL.md にこのガイドを追記すべき
   - **アルゴリズム側の対策（オプション）:** prev 末尾 ↔ next 先頭の包含検査を追加し、包含時は「prev を全部捨てて next を採用」する fallback decision を返す（YAGNI 判断は次回）

3. **Flash 品質が境界検出に致命的になり得る**
   - page-1 を Flash で読んだ時の誤字密度が高すぎ、Pro で読んだ page-2 とのトークン共通度が低くて MIN_SCORE=91 を下回った
   - page-1 を Pro で再 OCR した後でも、上記 (2) の包含問題で overlap 不検出 — つまり Flash 由来の誤字は本件の根本原因ではなかったが、見た目には見分けがつかなかった
   - **示唆:** 全ページ Pro 標準にすると $0.20/session 程度。要件の < ¥10 はクリア。「Flash → 疑義検知 → Pro」の二段運用は計算コストの節約にはなるが、品質要求が厳しい用途では Pro 標準も選択肢

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** F-13 救済では C 案（`apply-boundary-fix --replacement -` で空文字、マーカー除去のみ）を採用
  - **理由:** 今回の境界 0 は overlap 不検出 + 重複包含という、F-13 の想定範囲外（正常な OCR 揺らぎの吸収用）。重複削除は Markdown 編集で後でやる。F-13 にこのケース用の機能追加は YAGNI
  - **代替案:** B 案（page-1 を Pro で再 OCR してマージし直す）→ 実施したが (2) の包含問題で同じ結果 → C 案にフォールバック

- **判断:** 検出された 3 問題は今セッションでは修正せず、handover で次セッションに渡す
  - **理由:** 統合テストの「ゴール」は実機での通し動作確認とフロー検証。バグ・運用課題が出たこと自体が成果。今夜の時点で疲労と時刻（18:50）から、修正は別セッションで集中してやる方が安全
  - **代替案:** 即修正 → glob バグは 1 行修正だが、SKILL.md ガイド追加・Pro 標準化判断が絡むので一括での扱いが望ましい

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** `merge-save` 初回起動で `ValueError: invalid literal for int() with base 10: '2.ocr'`
  - **試したこと:** トレースバックを読み `_list_page_files` の glob `page-*.json` が OCR 中間ファイル（`page-1.ocr.json`, `page-2.ocr.json` など）も拾っていることを特定
  - **結果:** 中間ファイルを `_ocr_raw/` に手で退避してリトライ → 成功。ただし helper 自体のバグなので次セッションで修正必須

- **問題:** page-1↔page-2 で overlap が検出されず、Pro で再 OCR しても解決しなかった
  - **試したこと:** Flash → Pro 再 OCR の B 案を実施したが、`uncertain_boundaries` は依然 1
  - **結果:** 原因は OCR 品質ではなく、page-2 が page-1 を完全包含する撮影パターン。merge.py のオーバーラップアルゴリズムの構造的限界。撮影オペレーション側で防ぐのが現実的

- **問題:** page-1 を Flash で OCR した時、末尾の重要な行（記事の本文「機能的に見ても非常に優秀です。それらの機能を新たに操作を学ばずに今すぐ使いこなせるはずです。」）が誤読され「に当てはめずにすぐに使えるはずです。だって仕事でずっと使ってるんだもん。」というフラグメントに置き換わっていた
  - **試したこと:** Pro で再 OCR → ほぼ完璧に修正
  - **結果:** Flash は「画面端で行が切れている／インデント変則」あたりに弱い疑い。SKILL.md の疑義検知シグナル（インデント幅の急変・ASCII/全角混在）に「文の意味的不整合」を追加するか、Pro 標準化の根拠データになる

---

## 次にやること (Next Steps)

### 1. `_list_page_files` glob 修正（最優先・1 行）

1. [ ] `screen_read_helper.py:132` の `session_dir.glob("page-*.json")` を、save-page が生成する 3 桁ゼロパディング名（`page-001.json`〜）に限定するパターンへ変更
   - 候補 A: `glob("page-[0-9]*.json")` で `2.ocr` 系を除外
   - 候補 B: `glob("page-[0-9][0-9][0-9].json")` で 3 桁限定（より厳密）
2. [ ] テスト追加: OCR 中間ファイルが session_dir に共存しても正しい page-NNN.json だけ拾うこと

### 2. SKILL.md オペレーションガイド追記

3. [ ] 「PgDn 後の Up キー戻し量は 5〜10 行」を「3〜5 行（prev 末尾と next 先頭が確実に直接重なる範囲）」に厳しめへ
4. [ ] 「OCR 中間ファイル（`page-*.ocr.json`）は session_dir 直下ではなく `_ocr_raw/` サブディレクトリに保存」というフロー注記を追加（または上記 glob 修正で吸収）

### 3. Pro 標準化の検討

5. [ ] Flash 一次の品質問題（インデント変則や行端での誤読）が次の 1-2 セッションでも再現するか観察
6. [ ] 再現するなら一次から `gemini-2.5-pro` に切り替え（要件 < ¥10/session はクリア）。helper の `--model` デフォルトを Pro に変更し、Flash は試験的フォールバックとして残す案

### 4. 包含 boundary の救済（オプション・YAGNI 寄り）

7. [ ] merge.py で「prev 全体が next の先頭 K 行に部分文字列として含まれるか」をチェックし、含まれる場合「page-(N-1) を全部捨てる」decision を返す機能を追加するか検討
8. [ ] 上記 7 を入れない場合は、SKILL.md に「重複包含が起きた時の手動編集ガイド」を明記

### 5. 持ち越し（前回からの未対応）

9. [ ] `wifi-cam-mcp/.env` を削除
10. [ ] ルーターで C220 DHCP 固定割り当て（192.168.10.118）

---

## 参考情報

### 現在の構成スナップショット

| 項目 | 値 |
|------|-----|
| プロジェクト直下 | `/home/slmbrcat/projects/embodied-ai/` |
| C220 IP / プリセット | `192.168.10.118` / token=`"1"` name=`screen-read` |
| Vault 既定 | `~/obsidian-vault/00_Inbox/`（今回新規作成） |
| OCR 経路 | OpenRouter 直叩き |
| 一次モデル | `google/gemini-2.5-flash` ($0.002/page) — 今回 page-1 で品質問題 |
| 二次モデル | `google/gemini-2.5-pro` ($0.051/page) — 今回主力 |
| pytest 結果 | 23 passed (前セッションから変化なし) |
| 輝度ゲート | ✅ 実機通過（mean 113-119, std 70-74） |
| F-13 救済 UI | ✅ 動作確認（C 案: 空 replacement でマーカー除去） |
| 2 ページ統合テスト | ✅ 完走（4 ページ実走、ただし 3 件の宿題） |
| 残バグ | `_list_page_files` glob 衝突（要修正） |

### このセッションの実セッションディレクトリ（残置）

`/tmp/screen-read-20260429-165120/`
- `page-{1..4}.jpg` — 4 ページ撮影画像
- `page-00{1..4}.json` — save-page 結果
- `_ocr_raw/page-*.ocr.json` `_ocr_raw/page-*.pro.json` — 退避した OCR 中間ファイル
- 再起動で消える可能性あり。検証用に残したい場合は `docs/test-images/` 等にコピー

### 出力 Markdown

`/home/slmbrcat/obsidian-vault/00_Inbox/clip-20260429-1743.md`
- 4 ページ統合済み
- page1↔page2 領域に重複（行 33-55 付近）が残存。手動編集で削除可能
- frontmatter に `uncertain_boundaries: 1` の記録あり（救済後の更新は次セッションで検討）

### ドキュメント

- `docs/要件定義.md` — F-1〜F-16 機能要件
- `docs/アーキテクチャ.md` — シーケンス図
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260429-1850.md` — 本セッション直前のスナップショット
