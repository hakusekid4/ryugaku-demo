---
name: ai-config-memo
description: 会話の要点・決定・気づき・壁打ちの内容を、中央管理リポジトリ(hakusekid4/ai-config)に届けるために ai-config-inbox/ に保存する。「ai-config に記録して」「壁打ちを残して」「この会話を記録して」「中央に送って」と言われたとき、または本人の価値観・目標・ルールに関わる発言があったときに使う。
---

# ai-config への記録(受信箱方式)

このリポジトリの `ai-config-inbox/` に Markdown を 1 つ置くと、ai-config の同期が定期的に回収し、
`conversation-archive/inbox/<リポジトリ名>/` に集める。ai-config 側の AI がそれを読んでユーザー像・ルール・戦略に反映する。

## 手順

1. **何を残すか決める**。次のどれかに分類する。
   - `insight`: 本人の考え方・価値観・好みが分かる発言
   - `decision`: 決めたこと(ルール、方針、採否)
   - `question`: 本人に判断してもらう必要があること(その場で本人に聞かない。ai-config の台帳 `ai-systems/open-decisions.md` に積まれ、毎週日曜 21:00 の週次まとめでまとめて本人に出る)
   - `log`: 進捗や結果の報告(数字を含める)
   - `automation`: やり取りの最後の自動化探索(`/automation-scan`)で見つけた自動化の候補。ai-config の台帳 `ai-systems/automation-backlog.md` に積まれ、週次まとめの第 5 節で本人に出る
   - `project`: 新規プロジェクトの聞き取り(`/new-project`)の結果。ai-config 側が `projects/<スラッグ>/` に企画書を作る
   - `error`: **同じ失敗をくり返さないための記録。**本人に指摘された・やり直しになった・つまずいて時間を使ったこと。ai-config の `errors/log.jsonl` に入り、傾向が `ai-systems/error-lessons.md` にまとまって全リポジトリへ配られる(`ai-systems/error-learning.md`)
2. **他人の個人情報を伏せる**。氏名・連絡先・会社名は `[伏せ字]` に置き換える。本人の情報はそのままでよい。
3. **`ai-config-inbox/<YYYY-MM-DD>-<英語スラッグ>.md` に次の形式で書く**。同じ日に同じテーマがあれば追記する。

   ```markdown
   ---
   date: <YYYY-MM-DD>
   repo: <このリポジトリ名>
   kind: <insight | decision | question | log | automation | project | error>
   topic: <一言のテーマ>
   ---

   ## 要点

   - 3〜5 個の箇条書き。1 行 1 つ。数字があれば必ず入れる

   ## 経緯

   どういう文脈で出た話か。2〜5 行

   ## ai-config への反映案

   - どのファイル(user-profile / shared-rules / ai-systems)に何を足すか。分からなければ空欄でよい
   ```

   `kind: automation` のときは「要点」を台帳の 7 欄(ID は空でよい / 何を自動化するか / 今の手間(月に何回・1 回何分・誰が)/ 作るもの / 要るもの / なぜ即やらないか / 状態)にする。
   `kind: project` のときは「要点」を聞き取りの問と答えの一覧にし、「経緯」に仮で置いた値とその根拠を書く。
   `kind: error` のときは「要点」を 4 つにする。(1) 何をしようとして何が起きたか(エラー本文は 1〜3 行、**鍵やトークンは伏せる**)/
   (2) 原因 / (3) 次から AI が気をつけること(1 行)/ (4) 本人のプロンプトに助言があれば(無ければ「なし」)。
   自動で拾えている失敗(コマンドが落ちた等)は送らなくてよい。**送るのは人が指摘したこと**
   (「前にも言った」「また指示を読んでいない」「そのやり方は前に却下した」)。

4. **コミットしてプッシュする**。メッセージ例: `ai-config-inbox: <topic> を記録`。確認は取らない。
5. 返事は 2 行以内。「記録した。ファイル名は …」だけでよい。

## しないこと

- 会話の全文をそのまま貼らない。要点に絞る
- 他人の個人情報を残さない
- `AI-CONFIG.md` を直接書き換えない(同期で上書きされる)
