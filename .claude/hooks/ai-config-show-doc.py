#!/usr/bin/env python3
"""文書(.md / .txt)を新しく書いたら、その場で本人へ送るよう AI に促すフック(`PostToolUse`、Write)。

なぜ要るか(2026-10-09 本人「各セッションで作成されたテキストファイルを、出来たときに簡単に見れるようにしたい」
「全リポジトリでまとめずに」):

セッションが書いた報告・調査・計画は、リポジトリの中に置かれるだけで、本人は GitHub を開いて
探すしかなかった。Claude のアプリには `SendUserFile`(ファイルを本人の画面に出す道具。
`display: render` なら横の枠で中身がそのまま読める)がある。**新しく作った直後に送れば、
探さなくても届く。**AI が送るのを忘れないよう、仕組みが毎回差し込む。

- 促すのは**新しく作ったとき**だけ(Write の結果が create)。書き換えのたびに送ると同じファイルの札が並ぶ
- 配った共通設定・受信箱・生成物(`dist/`・`.claude/`・`ai-config-inbox/`・`conversation-archive/`)は促さない
- 作業用の使い捨て(途中の書き出し・控え)かどうかは AI が見て決める。迷ったら送る

全リポジトリへ配る(`scripts/ai_config_sync.py` の MANAGED_HOOKS)。配った先で単体で動くよう、
ほかのファイルを import しない。何が起きてもセッションを止めない(失敗したら何も出さずに終わる)。
止めたいときは環境変数 `AI_CONFIG_HOOKS=off`。
"""
from __future__ import annotations

import json
import os
import sys

EXTS = (".md", ".txt")
SKIP_PARTS = ("dist", ".claude", "ai-config-inbox", "conversation-archive", "node_modules", ".git")


def message(path: str) -> str:
    return (
        f"[ai-config フック] 文書を新しく作った: {path}\n"
        "本人が読む文書(報告・調査・計画・企画書など)なら、このターンの返事の前に "
        f'`SendUserFile`(files: ["{path}"]、display: "render"、status: 本人が見ているなら "normal"・'
        '定期起動など本人が見ていないなら "proactive"、caption: 何の文書か 1 行)で本人へ送る。'
        "作業用の使い捨て(途中の書き出し・台帳の控え)なら送らない。迷ったら送る。"
        "同じファイルを書き換えただけなら送り直さない(中身が大きく変わったときだけ)"
    )


def target(data: dict) -> str | None:
    if data.get("tool_name") != "Write":
        return None
    resp = data.get("tool_response")
    if not isinstance(resp, dict) or resp.get("type") != "create":
        return None
    inp = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    path = str(inp.get("file_path") or resp.get("filePath") or "")
    if not path.lower().endswith(EXTS):
        return None
    parts = path.replace("\\", "/").split("/")
    if any(p in SKIP_PARTS for p in parts[:-1]):
        return None
    root = os.environ.get("CLAUDE_PROJECT_DIR") or str(data.get("cwd") or "")
    if root and path.startswith(root.rstrip("/") + "/"):
        path = path[len(root.rstrip("/")) + 1:]
    return path


def main() -> int:
    try:
        if (os.environ.get("AI_CONFIG_HOOKS") or "").strip().lower() in ("off", "0", "false", "no"):
            return 0
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        path = target(data) if isinstance(data, dict) else None
        if path:
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PostToolUse", "additionalContext": message(path)}},
                ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
