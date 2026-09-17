#!/usr/bin/env python3
"""禁止事項を「文章のお願い」ではなく「仕掛け」で止める(PreToolUse フック)。

**なぜ要るか**(2026-09-17、D-007 の議論から)

`CLAUDE.md` と `AI-CONFIG.md` は命令ではなく**文脈**として渡る。公式ドキュメントにも
「Claude はそれを読んで従おうとするが、厳密な遵守は保証されない」「特定の時点で必ず
実行させたいものはフックにする。フックは Claude の判断に関係なく動く」とある。
`shared-rules/constraints.md` の禁止事項のうち、**取り返しのつかないもの**は文章に頼らず
ここで実際に止める。

**3 つの段階**

- `deny`: 取り返しがつかないもの。問答無用で止める(履歴の書き換え、危険な削除)
- `ask` : 本人の確認が要るもの(削除、外部への送信・公開)。本人が許可すれば通る
- 何も返さない: 通常の許可フローに任せる

**壊れたときの振る舞い**: 例外が出たら**通す**(exit 0、出力なし)。フックの不具合で
作業全体が止まるほうが害が大きいため。これは多層防御の 1 枚目で、最後の砦ではない。

入出力は Claude Code の PreToolUse の仕様どおり(https://code.claude.com/docs/en/hooks)。
標準入力に JSON、標準出力に `hookSpecificOutput` を返す。
"""
from __future__ import annotations

import json
import os
import re
import sys

# --------------------------------------------------------------------------
# 問答無用で止めるもの(取り返しがつかない)
# --------------------------------------------------------------------------
DENY_PATTERNS: list[tuple[str, str]] = [
    (r"\bgit\s+push\b[^|;&]*\s(--force\b|-f\b|--force-with-lease\b)",
     "git push --force は履歴の書き換えに当たるため禁止(constraints.md の禁止事項 4)。"
     "やり直したいときは打ち消しのコミットを積む。"),
    (r"\bgit\s+filter-branch\b|\bgit\s+filter-repo\b|\bgit-filter-repo\b",
     "filter-branch / filter-repo は履歴の書き換えそのもの(禁止事項 4)。"),
    (r"\bgit\s+reflog\s+(expire|delete)\b|\bgit\s+update-ref\s+-d\b",
     "reflog の削除は、やり直すための最後の記録を消す(禁止事項 4)。"),
    (r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf][a-zA-Z]*\s+(/|~|\$HOME|/home/?)\s*$",
     "ルート・ホームディレクトリの削除は禁止。"),
]

# --------------------------------------------------------------------------
# 本人に確認してから通すもの
# --------------------------------------------------------------------------
ASK_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*r",
     "ディレクトリの削除は本人の確認が要る(constraints.md: 削除は確認事項)。"),
    (r"\bgit\s+branch\s+(-D|-d\s+--force|--delete\s+--force)\b",
     "ブランチの削除は本人の確認が要る。"),
    (r"\bgit\s+push\b[^|;&]*(--delete\b|\s:\S)",
     "リモートのブランチ・タグの削除は本人の確認が要る。"),
    (r"\bgit\s+reset\s+--hard\b",
     "reset --hard は未コミットの変更を消す。2026-09-14 に実際に編集を失った"
     "(errors/log.jsonl)。先に commit か stash をしたか確認する。"),
    (r"\bgit\s+clean\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*f",
     "git clean -f は追跡されていないファイルを消す。"),
    (r"\b(gh|hub)\s+repo\s+delete\b",
     "リポジトリの削除は本人の確認が要る(2026-09-17 の本人指示でも削除は確認事項)。"),
]

# 外部への送信・公開に当たるツール(禁止事項 1)。本人の確認を挟む。
ASK_TOOLS: dict[str, str] = {
    "mcp__Gmail__send_message": "メールの送信は外部への発信に当たる(禁止事項 1)。",
    "mcp__Gmail__reply": "メールの返信は外部への発信に当たる(禁止事項 1)。",
    "mcp__Gmail__forward": "メールの転送は外部への発信に当たる(禁止事項 1)。",
    "mcp__Slack__slack_send_message": "Slack への投稿は外部への発信に当たる(禁止事項 1)。",
    "mcp__Slack__slack_schedule_message": "Slack への予約投稿も外部への発信に当たる。",
    "mcp__github__delete_file": "ファイルの削除は本人の確認が要る。",
}

# 削除に当たる MCP ツール名の共通部分(将来増えても拾えるように)
ASK_TOOL_REGEX: list[tuple[str, str]] = [
    (r"^mcp__.*__(delete|remove|destroy)_", "削除に当たる操作は本人の確認が要る。"),
]

# rm の対象がここなら確認しない(作業用の一時領域)
SAFE_RM_HINTS = ("/tmp/", "scratchpad", "__pycache__", "node_modules", ".pytest_cache")


# コマンドを包んで実行するもの。この中に危ないものが隠れていたら、引用符の中でも見る。
WRAPPERS = re.compile(r"\b(bash|sh|zsh)\s+-c\b|\beval\b|\bxargs\b")

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^\2\s*$", re.S | re.M)
_SQ = re.compile(r"'[^']*'")
_DQ = re.compile(r'"[^"]*"')


def _strip_literals(cmd: str) -> str:
    """ヒアドキュメントの中身と引用符で囲まれた文字列を消す。

    **これが無いと、禁止事項を文書に書く作業そのものが止まる。**2026-09-17 に確認した
    誤爆の実例(どれも日常の作業):
      - `cat > doc.md <<'EOF' ... git push --force は禁止 ... EOF`(規則を書く)
      - `git commit -m "git push --force は禁止と書いた"`(コミットメッセージ)
      - `grep -rn "git push --force" shared-rules/`(規則を探す)
    これらは「危ない命令」ではなく「危ない命令**について書いた文字列**」なので通す。
    """
    out = _HEREDOC.sub(" ", cmd)
    out = _SQ.sub(" ", out)
    out = _DQ.sub(" ", out)
    return out


def _is_scratch(cwd: str) -> bool:
    """作業ディレクトリが使い捨ての場所か。

    スクラッチ領域での `rm -rf tmpdir` のような掃除まで確認を挟むと、無人で動く
    定期実行が止まる。パスが相対でも判断できるように、作業ディレクトリ側を見る
    (2026-09-17 に `rm -rf hooktest` が止まって気づいた)。
    """
    c = (cwd or "").replace("\\", "/")
    return c.startswith("/tmp/") or c == "/tmp" or "scratchpad" in c


def _decide_bash(cmd: str, cwd: str = "") -> tuple[str, str] | None:
    # 文字列として書いてあるだけのものは見ない。ただし bash -c や eval で
    # 包んである場合は、引用符の中身も本物の命令なので元のまま見る。
    #
    # **ラッパーの判定は、文字列を除いたあとの本文で行う。**元の文字列で見ると、
    # 「`bash -c` で包んだものは捕まえる」のような**説明文**に反応して、
    # ヒアドキュメントの中身まで走査してしまう(2026-09-17、このフック自身が
    # その説明を台帳へ書く作業を誤って止めた)。
    stripped = _strip_literals(cmd)
    targets = [stripped]
    if WRAPPERS.search(stripped):
        targets.append(cmd)

    for target in targets:
        for pat, reason in DENY_PATTERNS:
            if re.search(pat, target):
                return "deny", reason
    for target in targets:
        for pat, reason in ASK_PATTERNS:
            if re.search(pat, target):
                if pat.startswith(r"\brm") and (
                        any(h in cmd for h in SAFE_RM_HINTS) or _is_scratch(cwd)):
                    continue
                return "ask", reason
    return None


def _decide_tool(tool: str, tool_input: dict) -> tuple[str, str] | None:
    if tool in ASK_TOOLS:
        return "ask", ASK_TOOLS[tool]
    for pat, reason in ASK_TOOL_REGEX:
        if re.search(pat, tool):
            return "ask", reason
    # 公開リポジトリの作成は本人が「公開」と言ったときだけ(2026-09-17 本人指示)
    if tool == "mcp__github__create_repository":
        private = tool_input.get("private")
        if private is False or str(private).lower() == "false":
            return "ask", ("公開リポジトリの作成は本人の確認が要る"
                           "(2026-09-17 本人指示: 既定は非公開、公開は本人が言ったときだけ)。")
    return None


def decide(payload: dict) -> tuple[str, str] | None:
    """(permissionDecision, 理由) を返す。判断しないときは None。"""
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    hit = _decide_tool(tool, tool_input)
    if hit:
        return hit
    if tool == "Bash":
        cmd = tool_input.get("command") or ""
        if isinstance(cmd, str) and cmd.strip():
            return _decide_bash(cmd, payload.get("cwd") or "")
    return None


def main() -> int:
    # 環境変数で丸ごと無効にできる(緊急時の逃げ道。既定は有効)
    if os.environ.get("AI_CONFIG_GUARD") == "off":
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:  # noqa: BLE001
        return 0  # 読めなければ通す(フックの不具合で作業を止めない)
    try:
        hit = decide(payload)
    except Exception as e:  # noqa: BLE001
        print(f"guard_prohibited: 判定中に例外(通します): {e}", file=sys.stderr)
        return 0
    if not hit:
        return 0
    decision, reason = hit
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": f"[ai-config の禁止事項] {reason}",
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
