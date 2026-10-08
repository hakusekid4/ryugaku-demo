#!/usr/bin/env python3
"""計画の詰め(`grill.md`)の書き方を機械で点検する。

**なぜ要るか**(2026-10-08): `grill.md` は手で書く。頭の `asked`(出した問の数)と
`next`(次の問)、各問の「答え」「決まったこと」「残したもの」を、1 問ごとに手で直す。
**どれか 1 つを忘れると、会話が切れたときに再開できない**(`next` だけが手がかり)。

もう 1 つ、**決定が実装側の文書に反映されないまま残る**型がある。
2026-10-08 に実物で踏んだ —— 骨格推定を DeepLabCut に決めた(10-05)のに
`requirements.txt` には「候補。相談後に決める」のまま別のライブラリが書かれており、
**そこを読んで入れると何も動かない**状態だった。
「残したもの」に挙げたファイルが**実在するか**までは、ここで確かめられる。

    python scripts/grill_lint.py docs/plans/<スラッグ>/grill.md
    python scripts/grill_lint.py docs/plans            # 下にある grill.md を全部

終了コード: 0 = 問題なし / 1 = 問題あり。
**中身の正しさは見ない。**書き方の食い違いだけ。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STATUSES = {"進行中", "完了", "打ち切り"}
#: 問の見出し。`### Q1 入力の単位`
Q_HEAD = re.compile(r"^### (Q\d+[a-z]?)\s+(.*)$", re.M)
#: 「残したもの」に挙がったパス。バッククォートで囲まれ、`/` か `.` を含むもの
PATH_IN_TICK = re.compile(r"`([^`\s]*[/.][^`\s]*)`")
#: 未回答の印
UNANSWERED = "(未)"


def front_matter(text: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+?)\s*(?:#.*)?$", text, re.M)
    return m.group(1).strip() if m else ""


def _blocks(text: str) -> list[tuple[str, str]]:
    """`(問の番号, その問の本文)` を並べて返す。"""
    heads = list(Q_HEAD.finditer(text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append((m.group(1), text[m.end():end]))
    return out


def _answered(body: str) -> bool:
    m = re.search(r"^- \*\*答え\*\*:\s*(.*)$", body, re.M)
    return bool(m) and UNANSWERED not in m.group(1)


def lint_one(path: Path) -> list[str]:
    """1 枚ぶんの問題を並べて返す。空なら問題なし。"""
    text = path.read_text(encoding="utf-8")
    where = path.as_posix()
    out: list[str] = []

    status = front_matter(text, "status")
    if status not in STATUSES:
        out.append(f"{where}: status が {sorted(STATUSES)} のどれでもない: {status!r}")

    blocks = _blocks(text)
    if not blocks:
        out.append(f"{where}: `### Q1 …` の形の問が 1 つも無い")
        return out

    asked = front_matter(text, "asked")
    if asked.isdigit() and int(asked) != len(blocks):
        out.append(f"{where}: asked が {asked} だが、問は {len(blocks)} 個ある")

    answered = [q for q, b in blocks if _answered(b)]
    pending = [q for q, b in blocks if not _answered(b)]

    nxt = front_matter(text, "next")
    if pending:
        if pending[0] not in nxt:
            out.append(
                f"{where}: next が {nxt!r} だが、答え待ちの最初の問は {pending[0]}。"
                "**会話が切れたとき、ここだけが再開の手がかり**")
        if status == "完了":
            out.append(f"{where}: status が 完了 だが、答え待ちの問がある: {pending}")
    elif status == "進行中" and not re.search(r"to-spec|完了|空", nxt):
        out.append(
            f"{where}: 全部答えが出ているのに status が 進行中 で next が {nxt!r}。"
            "締めるなら status を 完了 にし、next に次の手を書く")

    # 答えが出ている問には「決まったこと」が要る
    for q, body in blocks:
        if not _answered(body):
            continue
        if "- **決まったこと**" not in body:
            out.append(f"{where}: {q} に答えがあるのに「決まったこと」が無い")
        # 「残したもの」に挙げたファイルは実在すること
        m = re.search(r"^- \*\*残したもの\*\*:\s*(.*)$", body, re.M)
        if not m:
            continue
        for rel in PATH_IN_TICK.findall(m.group(1)):
            if rel.startswith(("http", "#")) or " " in rel:
                continue
            for base in (path.parent, path.parent.parent, path.parent.parent.parent,
                         Path.cwd()):
                if (base / rel).exists():
                    break
            else:
                out.append(
                    f"{where}: {q} の「残したもの」に挙げた {rel} が見つからない。"
                    "**決定が実装側に反映されていない恐れ**")
    return out


def find(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(target.rglob("grill.md"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default="docs/plans",
                    help="grill.md か、その上のフォルダ(既定 docs/plans)")
    a = ap.parse_args(argv)
    target = Path(a.path)
    if not target.exists():
        print(f"無い: {target}", file=sys.stderr)
        return 2
    files = find(target)
    if not files:
        print(f"grill.md が見つからない: {target}")
        return 0
    msgs: list[str] = []
    for f in files:
        msgs += lint_one(f)
    for m in msgs:
        print("NG  " + m)
    print(f"計画 {len(files)} 枚 / 問題 {len(msgs)} 件")
    return 1 if msgs else 0


if __name__ == "__main__":
    raise SystemExit(main())
