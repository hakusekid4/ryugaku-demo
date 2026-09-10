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
   - `question`: ai-config 側で判断してほしいこと
   - `log`: 進捗や結果の報告(数字を含める)
2. **他人の個人情報を伏せる**。氏名・連絡先・会社名は `[伏せ字]` に置き換える。本人の情報はそのままでよい。
3. **`ai-config-inbox/<YYYY-MM-DD>-<英語スラッグ>.md` に次の形式で書く**。同じ日に同じテーマがあれば追記する。

   ```markdown
   ---
   date: <YYYY-MM-DD>
   repo: <このリポジトリ名>
   kind: <insight | decision | question | log>
   topic: <一言のテーマ>
   ---

   ## 要点

   - 3〜5 個の箇条書き。1 行 1 つ。数字があれば必ず入れる

   ## 経緯

   どういう文脈で出た話か。2〜5 行

   ## ai-config への反映案

   - どのファイル(user-profile / shared-rules / ai-systems)に何を足すか。分からなければ空欄でよい
   ```

4. **コミットしてプッシュする**。メッセージ例: `ai-config-inbox: <topic> を記録`。確認は取らない。
5. 返事は 2 行以内。「記録した。ファイル名は …」だけでよい。

## しないこと

- 会話の全文をそのまま貼らない。要点に絞る
- 他人の個人情報を残さない
- `AI-CONFIG.md` を直接書き換えない(同期で上書きされる)
