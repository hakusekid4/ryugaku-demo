#!/usr/bin/env python3
"""チケット(docs/plans/<スラッグ>/tickets/NN-*.md)の前線と書き方を点検する(AUT-063)。

前線 = 状態が ready-for-agent で、依存がすべて done のチケット。`/run-ticket` と
定期起動が手で判定していた部分を置き換える。書き方は `/to-tickets` の型に従う。

    python scripts/tickets.py frontier docs/plans/<スラッグ>   # 前線を番号順に出す
    python scripts/tickets.py lint docs/plans/<スラッグ>       # 書き方の点検
    python scripts/tickets.py goal <チケットのファイル>        # 中身入りの /goal の 1 行を出す
    python scripts/tickets.py goal docs/plans/<スラッグ>       # 計画まとめて回す /goal の 1 行を出す
    python scripts/tickets.py fill-goals docs/plans/<スラッグ> # 着手前のチケットの /goal 欄を作り直す

/goal の 1 行(2026-10-06 本人「自動で作る goal が短すぎる」): 前はチケットのファイル名と
「完了条件が通る」だけで、/goal の判定役は何を作るか・何で確かめるかを知らずに回っていた。
いまは題・作るもの・完了条件のコマンド全部・止まり方を 1 行に入れる。

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


def _now() -> str:
    """いまの日本時間。`2026-10-06 13:50(JST)` の形。"""
    from datetime import datetime, timedelta, timezone

    jst = datetime.now(timezone(timedelta(hours=9)))
    return jst.strftime("%Y-%m-%d %H:%M(JST)")


GOAL_HEAD = "## /goal"
STOP = ("/run-ticket の「止まってよいとき」(同じ失敗 3 回・着手から 2 時間・本人の判断が要る・完了条件が誤っている)"
        "に当たり、状態が ready-for-human になって「記録」に `- 止めた:` の 1 行で理由と次の案が書いてある。"
        "テストや完了条件を緩めて通さない")


GOAL_MAX = 4000   # /goal の条件の上限(code.claude.com/docs/en/goal、2026-10-06 確認)
BUILD_MAX = 1200  # 作るものはここで切る(完了条件と止まり方を必ず残すため)


def _section(text: str, head: str) -> str:
    m = re.search(rf"^## {re.escape(head)}[^\n]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def _commands(checks: list[str]) -> list[str]:
    out = []
    for c in checks:
        if "本人確認" in c:
            continue
        out += re.findall(r"`[^`]+`", c)
    return out


def _rel(path: Path) -> str:
    parts = Path(path).resolve().parts
    return "/".join(parts[parts.index("docs"):]) if "docs" in parts else str(path)


def goal_for_ticket(path: Path) -> str:
    """チケット 1 枚から、そのまま貼れる中身入りの /goal の 1 行を作る。"""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^# \d+:\s*(.+)$", text, re.M)
    title = m.group(1).strip() if m else path.stem
    build = " ".join(ln.strip() for ln in _section(text, "作るもの").splitlines() if ln.strip())
    if len(build) > BUILD_MAX:
        build = build[:BUILD_MAX] + "…(続きはチケット本文)"
    cmds = _commands(_checks(text))
    conds = "、".join(f"{c} が通る" for c in cmds) if cmds else "(コマンドが無い。lint で直す)"
    return _cap(f"/goal {_rel(path)}「{title}」を /run-ticket の手順(着手を記す → /tdd → 完了条件を全部走らせる → "
            f"見直し → 閉じる)で片付ける。作るもの: {build} 完了の判定: {conds}。"
            f"各コマンドを実際に走らせ、終了コードと出力の要点を会話に示している(判定役は会話しか読まない)。"
            f"そのうえでチケットの状態が done になり、「記録」に `- 閉じた:` の 1 行(日本時間と結果)がある。"
            f"または、{STOP}")


def _cap(g: str) -> str:
    if len(g) > GOAL_MAX:
        raise ValueError(f"/goal の 1 行が {len(g)} 字で上限 {GOAL_MAX} 字を超える。完了条件を減らすかチケットを割る")
    return g


def goal_for_plan(plan: Path) -> str:
    """計画フォルダの前線が空になるまで、チケットを 1 枚ずつ片付け続ける /goal の 1 行。"""
    plan = Path(plan)
    if plan.name == "tickets":
        plan = plan.parent
    ts = load(plan)
    left = [f"{t.num}" for t in ts if t.state not in {"done", "wontfix"}]
    rel = _rel(plan)
    return _cap(f"/goal {rel} のチケット(残り {', '.join(left) or 'なし'})を、`python scripts/tickets.py frontier {rel}`"
            f"(ai-config 以外は `python .claude/tools/tickets.py`)の前線の先頭から 1 枚ずつ /run-ticket の手順で"
            f"片付け、各チケットの「完了条件」のコマンドを全部走らせて終了コードと出力の要点を会話に示し、"
            f"done にして「記録」に `- 閉じた:` を書く。"
            f"1 枚ごとにコミットして push する。前線が空になったら終わり。1 枚が止まってよいとき"
            f"(同じ失敗 3 回・着手から 2 時間・本人の判断が要る)に当たったら、そのチケットを ready-for-human にして"
            f"「記録」に `- 止めた:` の 1 行を書き、残りの前線へ進む。テストや完了条件を緩めて通さない")


def fill_goals(path: Path) -> int:
    """着手前(ready-for-agent)のチケットの /goal 欄を goal_for_ticket の 1 行に入れ替える。数を返す。"""
    n = 0
    for t in load(Path(path)):
        if t.state != "ready-for-agent":
            continue
        text = t.path.read_text(encoding="utf-8")
        block = f"{GOAL_HEAD}(貼るだけで回る)\n{goal_for_ticket(t.path)}\n\n"
        m = re.search(rf"^{re.escape(GOAL_HEAD)}[^\n]*$.*?(?=^## |\Z)", text, re.M | re.S)
        if m:
            new = text[:m.start()] + block + text[m.end():]
        else:
            r = re.search(r"^## 記録", text, re.M)
            new = text[:r.start()] + block + text[r.start():] if r else text.rstrip() + "\n\n" + block
        if new != text:
            t.path.write_text(new, encoding="utf-8")
            n += 1
    return n


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
        if t.state == "ready-for-agent":
            goal = _section(t.path.read_text(encoding="utf-8"), "/goal")
            missing = [c for c in _commands(t.checks) if c not in goal]
            if goal and missing:
                msgs.append(f"{name}: /goal の 1 行が短い(完了条件の {', '.join(missing)} が入っていない)。"
                            f"`tickets.py fill-goals` で作り直す")
    graph = {t.num: t.deps for t in ts}

    def cyclic(n: str, seen: tuple[str, ...]) -> bool:
        if n in seen:
            return True
        return any(cyclic(d, seen + (n,)) for d in graph.get(n, []))

    loops = sorted(n for n in graph if cyclic(n, ()))
    if loops:
        msgs.append(f"依存が循環している: {', '.join(loops)}")
    return msgs


def set_state(path: Path, state: str) -> None:
    """チケットの「状態」を書き換える。"""
    if state not in STATES:
        raise ValueError(f"知らない状態: {state}。{sorted(STATES)} のどれか")
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r"^- 状態:\s*.+$", f"- 状態: {state}", text, count=1, flags=re.M)
    if not n:
        raise ValueError(f"「- 状態:」の行が無い: {path}")
    path.write_text(new, encoding="utf-8")


def _append_record(path: Path, line: str) -> None:
    """「## 記録」の末尾に 1 行足す。節が無ければ作る。"""
    text = path.read_text(encoding="utf-8").rstrip("\n")
    if not re.search(r"^## 記録\s*$", text, re.M):
        text += "\n\n## 記録"
    path.write_text(text + "\n" + line + "\n", encoding="utf-8")


def start(path: Path, when: str) -> None:
    """着手を記す。状態を in-progress にし、「記録」に `- 着手:` を足す。"""
    set_state(path, "in-progress")
    _append_record(path, f"- 着手: {when}")


def close(path: Path, when: str, note: str, *, tick: bool = True) -> None:
    """閉じる。状態を done にし、完了条件に印を付け、`- 閉じた:` を足す。

    **手で 4 か所を直していた**(状態・印・記録・一覧の表)。
    5 枚続けて同じことをしたので道具にした(2026-10-06 の自動化探索)。
    `tick=False` にすると印は付けない(本人確認が残っているときなど)。
    """
    if tick:
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^## 完了条件\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
        if m:
            body = re.sub(r"^(\s*)- \[ \]", r"\1- [x]", m.group(1), flags=re.M)
            path.write_text(text[: m.start(1)] + body + text[m.end(1) :], encoding="utf-8")
    set_state(path, "done")
    _append_record(path, f"- 閉じた: {when}。{note}")


def update_readme(plan: Path) -> int:
    """`tickets/README.md` の表の状態を、チケットの実際の状態に合わせる。

    **表とチケットがずれるのがいちばん困る。**読む人は表しか見ない。
    """
    folder = Path(plan)
    if (folder / "tickets").is_dir():
        folder = folder / "tickets"
    readme = folder / "README.md"
    if not readme.is_file():
        return 0
    text = readme.read_text(encoding="utf-8")
    n = 0
    for t in load(folder):
        # | 04 | 題 | 依存 | 状態 |
        pat = rf"^(\|\s*{t.num}\s*\|[^|]*\|[^|]*\|\s*)([^|]*?)(\s*\|)$"

        def repl(m: re.Match) -> str:
            shown = "**done**" if t.state == "done" else t.state
            # 「**done**(本人確認だけ残り)」のような補足は残す
            tail = m.group(2).strip()
            if t.state == "done" and tail.startswith("**done**"):
                return m.group(0)
            return m.group(1) + shown + m.group(3)

        text, k = re.subn(pat, repl, text, count=1, flags=re.M)
        n += k
    readme.write_text(text, encoding="utf-8")
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "cmd",
        choices=["frontier", "lint", "goal", "fill-goals", "start", "close", "readme"],
    )
    ap.add_argument("path")
    ap.add_argument("--when", default="", help="start / close のとき、日本時間")
    ap.add_argument("--note", default="", help="close のとき、結果の 1 行")
    ap.add_argument(
        "--no-tick", action="store_true",
        help="close のとき、完了条件の印を付けない(本人確認が残っているときなど)",
    )
    a = ap.parse_args(argv)
    if a.cmd in {"start", "close"}:
        when = a.when or _now()
        p = Path(a.path)
        if a.cmd == "start":
            start(p, when)
            print(f"着手を記した: {p}({when})")
        else:
            if not a.note:
                print("--note に結果の 1 行を渡す", file=sys.stderr)
                return 2
            close(p, when, a.note, tick=not a.no_tick)
            print(f"閉じた: {p}({when})")
            print(f"一覧の表を直した: {update_readme(p.parent)} 行")
        return 0
    if a.cmd == "readme":
        print(f"一覧の表を直した: {update_readme(Path(a.path))} 行")
        return 0
    if a.cmd == "goal":
        p = Path(a.path)
        print(goal_for_ticket(p) if p.is_file() else goal_for_plan(p))
        return 0
    if a.cmd == "fill-goals":
        print(f"/goal を作り直した: {fill_goals(Path(a.path))} 枚")
        return 0
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
