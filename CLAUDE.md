# CLAUDE.md

*このリポジトリで動く AI への指示書。固有の指示はこのファイルの上部に書く。*

<!-- ai-config:begin -->
## ai-config(共通設定)

このリポジトリで動く AI は、起動時に次の 3 つを必ず読む。

1. このファイル(`CLAUDE.md`)。リポジトリ固有の指示
2. `AI-CONFIG.md`。hakusekid4/ai-config から自動同期される共通設定。**手で編集しない**(同期で上書きされる)
3. `README.md`。プロジェクト概要

矛盾したときの優先順位: 法令・利用規約 > `AI-CONFIG.md` の禁止事項 > `CLAUDE.md` > `AI-CONFIG.md` のその他 > `README.md`

会話の要点や決定を中央に残したいときは `/ai-config-memo` を使う。`ai-config-inbox/` に保存され、ai-config が定期的に回収する。
<!-- ai-config:end -->
