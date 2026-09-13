# CLAUDE.md

*このリポジトリで動く AI への指示書。固有の指示はこのファイルの上部に書く。*

<!-- ai-config:begin -->
## ai-config(共通設定)

@AI-CONFIG.md

上の 1 行は Claude Code の import 記法。これがあると、共通設定 `AI-CONFIG.md` はセッション開始時に
**自動で**読み込まれる(AI が自分で開く必要はない)。この行を消さない。

このリポジトリで動く AI が起動時に読むもの。

1. このファイル(`CLAUDE.md`)。リポジトリ固有の指示
2. `AI-CONFIG.md`。hakusekid4/ai-config から自動同期される共通設定。上の import で自動読み込み。**手で編集しない**(同期で上書きされる)
3. `README.md`。プロジェクト概要

矛盾したときの優先順位: 法令・利用規約 > `AI-CONFIG.md` の禁止事項 > `CLAUDE.md` > `AI-CONFIG.md` のその他 > `README.md`

会話の要点や決定を中央に残したいときは `/ai-config-memo` を使う。`ai-config-inbox/` に保存され、ai-config が定期的に回収する。
本人に判断してもらうことは**その場で聞かず**、`/ai-config-memo`(kind: question)で送る。週次まとめでまとめて本人に出る。

### やり取りの最後に必ずすること

**手を動かした(ファイルを変えた・コマンドを実行した)やり取りの最後に、毎回「自動化できること」を探す。** 手順は `/automation-scan`、ルールは `AI-CONFIG.md` の第 4 節。報告は 1〜3 行で、必ず「自動化の探索:」で書き出す。本人の判断が要る案はその場で聞かず、`/ai-config-memo`(`kind: automation`)で受信箱へ送る。

### 新しいプロジェクトの相談を受けたら

**作業を始める前に、1 問 1 答の聞き取りに入る。** 手順は `/new-project`、ルールは `AI-CONFIG.md` の第 5 節。1 回の返答で聞くのは 1 問だけ。計画そのものは ai-config の `projects/` に置くので、結果は `/ai-config-memo`(`kind: project`)で送る。

### 読み込まれているか疑わしいとき

`/context` の Memory files に `CLAUDE.md` と `AI-CONFIG.md` が並んでいるかを見る。
無ければ、作業ディレクトリがリポジトリ直下でない可能性が高い(CLAUDE.md は「起動したディレクトリとその上位」からしか自動で読まれない)。
<!-- ai-config:end -->
