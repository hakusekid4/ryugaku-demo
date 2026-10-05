#!/usr/bin/env python3
"""チケット(docs/plans/<スラッグ>/tickets/NN-*.md)の前線と書き方を点検する(AUT-063)。

前線 = 状態が ready-for-agent で、依存がすべて done のチケット。`/run-ticket` と
定期起動が手で判定していた部分を置き換える。書き方は `/to-tickets` の型に従う。

    python scripts/tickets.py frontier docs/plans/<スラッグ>   # 前線を番号順に出す
    python scripts/tickets.py lint docs/plans/<スラッグ>       # 書き方の点検

終了コード: frontier = 0(前線が空でも 0)/ lint = 0 問題なし・1 問題あり
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATES = {"ready-for-agent", "ready-for-human", "in-progress", "done", "wontfix"}


@dataclass
class Ticket:
    num: str
    path: Path
    state: str
    deps: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


def _field(text: str, name: str) -> str:
    m = re.search(rf"^- {name}:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def _checks(text: str) -> list[str]:
    m = re.search(r"^## 完了条件\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip().startswith("- [")]


def load(path: Path) -> list[Ticket]:
    """フォルダ(`tickets/` でも、その親の計画フォルダでもよい)からチケットを読む。"""
    path = Path(path)
    if (path / "tickets").is_dir():
        path = path / "tickets"
    out = []
    for f in sorted(path.glob("[0-9][0-9]-*.md")):
        text = f.read_text(encoding="utf-8")
        deps_raw = _field(text, "依存")
        deps = [] if deps_raw.startswith("なし") else re.findall(r"\b(\d{2})\b", deps_raw)
        out.append(Ticket(f.name[:2], f, _field(text, "状態"), deps, _checks(text)))
    return out


def frontier(ts: list[Ticket]) -> list[Ticket]:
    done = {t.num for t in ts if t.state == "done"}
    return [t for t in ts if t.state == "ready-for-agent" and all(d in done for d in t.deps)]


def _has_command(line: str) -> bool:
    return "`" in line


def lint(ts: list[Ticket]) -> list[str]:
    msgs = []
    nums = {t.num for t in ts}
    for t in ts:
        name = t.path.name
        if t.state not in STATES:
            msgs.append(f"{name}: 状態「{t.state or '(無し)'}」は使えない({' / '.join(sorted(STATES))})")
        for d in t.deps:
            if d not in nums:
                msgs.append(f"{name}: 依存 {d} のチケットが無い")
        machine = [c for c in t.checks if "本人確認" not in c]
        if t.state in {"ready-for-agent", "in-progress"} and not any(_has_command(c) for c in machine):
            msgs.append(f"{name}: 完了条件にコマンド(`…`)が 1 つも無い。/goal で判定できない")
    graph = {t.num: t.deps for t in ts}

    def cyclic(n: str, seen: tuple[str, ...]) -> bool:
        if n in seen:
            return True
        return any(cyclic(d, seen + (n,)) for d in graph.get(n, []))

    loops = sorted(n for n in graph if cyclic(n, ()))
    if loops:
        msgs.append(f"依存が循環している: {', '.join(loops)}")
    return msgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["frontier", "lint"])
    ap.add_argument("path")
    a = ap.parse_args(argv)
    ts = load(Path(a.path))
    if a.cmd == "frontier":
        fr = frontier(ts)
        if not fr:
            waiting = [f"{t.path.name}({t.state})" for t in ts if t.state not in {"done", "wontfix"}]
            print("前線は空。残り: " + (", ".join(waiting) if waiting else "なし(全部終わった)"))
        for t in fr:
            print(t.path)
        return 0
    msgs = lint(ts)
    for m in msgs:
        print("NG  " + m)
    print(f"チケット {len(ts)} 枚 / 問題 {len(msgs)} 件")
    return 1 if msgs else 0


if __name__ == "__main__":
    sys.exit(main())
