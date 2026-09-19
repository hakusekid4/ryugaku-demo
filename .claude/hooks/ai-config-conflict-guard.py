#!/usr/bin/env python3
"""競合マーカーが残ったままのコミットを止める(PreToolUse フック)。

**なぜ要るか**: マージが競合したあと `git add -A` をすると、`<<<<<<<` を含むファイルが
そのままステージされ、気づかずにコミット・push まで通ってしまう。**2026-09-14 と
2026-09-17 の 2 回、実際にやった。**どちらも後から手で直している。

「気をつける」では止まらないので、コミットの直前に機械的に見る。

- `git commit` を含むコマンドのときだけ働く
- ステージされた中身に競合マーカーがあれば `deny`
- git が使えない・判定できないときは通す(フックの不具合で作業を止めない)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# 本物の競合は 3 種のマーカーが**行頭に**そろって現れる。
# 部分一致で見ると、マーカーを扱うコードや試験データを競合と誤認する
# (2026-09-17、同じ作りの `sync_branch.py` が自分自身のソースで誤爆した)。
_BEGIN = re.compile(r"^<<<<<<< ", re.M)
_MID = re.compile(r"^=======\s*$", re.M)
_END = re.compile(r"^>>>>>>> ", re.M)


def has_conflict(text: str) -> bool:
    """本物の競合マーカーが残っているか。"""
    return bool(_BEGIN.search(text) and _MID.search(text) and _END.search(text))
# `git commit` を含むか。`--amend` も対象。文字列の中の "git commit" には反応しないよう、
# 行頭か区切り記号の直後にあるものだけを見る。
COMMIT_RE = re.compile(r"(^|[;&|]\s*|\(\s*)git\s+(-c\s+\S+\s+)*commit\b")

# `cd /path && git commit ...` の形。フックには**セッションの**作業ディレクトリしか
# 渡らないため、コマンド側で移動している場合はそちらを見ないと index を読み違える
# (2026-09-17 に、別のリポジトリでのコミットを見逃して気づいた)。
CD_RE = re.compile(r"^\s*cd\s+(\"[^\"]+\"|'[^']+'|\S+)\s*(?:&&|;)")


def effective_cwd(cmd: str, cwd: str) -> str:
    m = CD_RE.match(cmd)
    if not m:
        return cwd
    path = m.group(1).strip("\"'")
    if os.path.isabs(path) and os.path.isdir(path):
        return path
    joined = os.path.join(cwd or "", path)
    return joined if os.path.isdir(joined) else (cwd or "")


def staged_files(cwd: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                         cwd=cwd, capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        return []
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def conflicted(cwd: str, path: str) -> bool:
    """ステージされた中身(作業ファイルではなく index の中身)を見る。"""
    out = subprocess.run(["git", "show", f":{path}"], cwd=cwd,
                         capture_output=True, text=True, timeout=15, errors="replace")
    if out.returncode != 0:
        return False
    return has_conflict(out.stdout)


def _blob(cwd: str, rev_path: str) -> str:
    out = subprocess.run(["git", "rev-parse", "--verify", "-q", rev_path], cwd=cwd,
                         capture_output=True, text=True, timeout=15)
    return out.stdout.strip() if out.returncode == 0 else ""


def unchanged_from_parent(cwd: str, path: str) -> bool:
    """ステージされた中身が、コミットの親(HEAD か、マージ中なら MERGE_HEAD)のどちらかと同じか。

    マージのコミットでは相手側の全ファイルがステージされる。その中に、試験データとして
    本物と同じ形の競合マーカーを含むファイル(`scripts/tests/test_merge_ledgers.py`)があり、
    2026-09-19 に `main` の取り込みが止まった。自分が触っていないファイルは、相手側で
    既に通ったものなので見ない。**自分が変えた(どの親とも違う)ファイルだけを見る。**
    """
    staged = _blob(cwd, f":{path}")
    if not staged:
        return False
    for parent in ("HEAD", "MERGE_HEAD"):
        if _blob(cwd, f"{parent}:{path}") == staged:
            return True
    return False


def check(cwd: str) -> list[str]:
    bad = []
    for path in staged_files(cwd):
        try:
            if unchanged_from_parent(cwd, path):
                continue
            if conflicted(cwd, path):
                bad.append(path)
        except Exception:  # noqa: BLE001
            continue
    return bad


def main() -> int:
    if os.environ.get("AI_CONFIG_GUARD") == "off":
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:  # noqa: BLE001
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not isinstance(cmd, str) or not COMMIT_RE.search(cmd):
        return 0
    cwd = effective_cwd(cmd, payload.get("cwd") or os.getcwd())
    try:
        bad = check(cwd)
    except Exception as e:  # noqa: BLE001
        print(f"block_conflict_markers: 判定中に例外(通します): {e}", file=sys.stderr)
        return 0
    if not bad:
        return 0
    names = "、".join(bad[:5]) + ("ほか" if len(bad) > 5 else "")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"[ai-config] 競合マーカーが残ったままコミットしようとしている: {names}。"
            "マージの競合を解消してから commit する。"
            "生成物なら作り直すか、`git checkout <正しい側> -- <パス>` で戻す。"),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
