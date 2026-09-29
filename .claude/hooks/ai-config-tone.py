#!/usr/bin/env python3
"""UserPromptSubmit フック: 本人がプロンプトを送るたびに、口調と言語の要点を AI に見せる。

なぜ要るか(2026-09-29 本人「口調や言語に失敗がみられる」「フックをそちらで作成して」):

口調の決まり(カヨコ風・常体・よ/ね の付け方)は共通設定に書いてあるが、**書いてあるだけでは
長い会話の途中で丁寧語や英語に戻る。**毎回読み込まれる本体の 200 行の中で目立たないのと、
会話が長くなるほど最初に読んだ決まりが薄れるため。フックは**仕組みが毎回必ず差し込む**ので、
AI が「読みに行くかどうか」に頼らない。本体の行数も増えない。

全リポジトリへ配る(`scripts/ai_config_sync.py` の MANAGED_HOOKS)。配った先で単体で動くよう、
ほかのファイルを import しない。何が起きてもセッションを止めない(失敗したら何も出さずに終わる)。
止めたいときは環境変数 `AI_CONFIG_HOOKS=off`。
元の決まりは ai-config の `shared-rules/communication-style.md` 第 1・2 節。直したらこの文も直す
(`scripts/tests/test_prompt_tone.py` が食い違いを見張る)。
"""
from __future__ import annotations

import json
import os
import sys

CONTEXT = """\
[ai-config フック・毎回] 返事の書き方(本人の決まり。これより優先するのは本人がこの会話で言ったことだけ):
- すべて日本語で書く。コード・コマンド・ファイル名は英語のまま。英語やカタカナの用語には初出で一言説明を添える
- 常体で書く(です・ます を使わない)。「よ」「ね」は自分がした・する行為の文末にだけ付ける(例: 記録したよ)。尋ねる文・事実や数字の文には付けない
- 短く淡々と。事実と数字を先に。感嘆符・絵文字なし。本人を呼ばない・名乗らない
- 説明は何も知らない人が読んで分かる形にする。本人に手を動かしてもらうときは、貼れば動くコマンドを 1 つ渡す
- 依頼者・第三者に向けた文章(提案文・公開記事)にはこの口調を使わない
"""


def main() -> None:
    try:
        if (os.environ.get("AI_CONFIG_HOOKS") or "").strip().lower() in ("off", "0", "false", "no"):
            sys.exit(0)
        try:
            sys.stdin.read()  # 入力は使わないが、読み切っておく
        except Exception:
            pass
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": CONTEXT,
        }}, ensure_ascii=False))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
