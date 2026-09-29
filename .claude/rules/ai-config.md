<!-- このファイルは hakusekid4/ai-config が自動配布する。手で編集しない(次の同期で上書きされる) -->
# ai-config(共通設定)

*`.claude/rules/` に置いた Markdown は、`CLAUDE.md` とは別経路でセッション開始時に必ず読み込まれる。
`CLAUDE.md` が消えた・書き換えられた・読み込まれなかったときの二重化。*

- **共通設定の正本はこのリポジトリ直下の `AI-CONFIG.md`**(hakusekid4/ai-config から自動同期)。
  `CLAUDE.md` の `@AI-CONFIG.md` で自動読み込みされる。もし読み込まれていなければ、**最初に `AI-CONFIG.md` を開いて読む**。
- 矛盾したときの優先順位: 法令・利用規約 > `AI-CONFIG.md` の禁止事項 > `CLAUDE.md` > `AI-CONFIG.md` のその他 > `README.md`
- **本人に判断してもらうことは、その場で聞かない。** `/ai-config-memo`(kind: question)で ai-config へ送る。
  毎週日曜 21:00 の週次まとめでまとめて本人に出る。例外は期限が次の日曜より前のもの、外部への投稿・応募・送金・発注、履歴の書き換え・削除。
- 会話の要点・決定・気づき・進捗も `/ai-config-memo` で ai-config へ送る(`ai-config-inbox/` に置くと同期が回収する)。
- `AI-CONFIG.md`、`CLAUDE.md` の `ai-config` ブロック、このファイルは手で編集しない。直したいことがあれば ai-config 側を直す。

<!-- lessons:begin -->
### よくある失敗(ai-config が集計。くり返している上位 5 件まで)

- **検査が自分自身に反応した**(2 回 / keibaAI-V4): 文字列や記号の有無で見張る検査は、**その文字列を正しく扱っているコード自身**にも当たる。行頭の形・3 種そろっているか・引用符やヒアドキュメントの外か、で絞る。作ったら必ず自分のリポジトリ全体にかけて、0 件になることを確かめる。
<!-- lessons:end -->
