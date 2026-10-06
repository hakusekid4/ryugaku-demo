#!/usr/bin/env python3
"""保存された `list_triggers` の結果から、あるセッションに紐づく定期起動を取り出す。

なぜ要るか(2026-10-06):

`/daily-page` の手順 1 は「`list_triggers` で `persistent_session_id` が自分のものを拾い、
時刻(日本時間)+ 1 行にする」と決まっている。ところが `list_triggers` の出力は
**7 万字を超えて会話に入らない**ので、毎回ファイルに保存され、そこから
その場で書いた Python で取り出すことになる。入れ物の形が
`{"data": [...]}`(件数は `has_more` / `next_cursor` と並ぶ)で、
**鍵を取り違えると 0 件と出て、定期起動が「無し」のページができる。**
実際に 2026-10-06 に 1 回取り違えた。形の扱いをここ 1 か所に寄せる。

使い方:

    python scripts/session_triggers.py <保存されたファイル> --session <セッションID>
    python scripts/session_triggers.py <ファイル> --session <ID> --md   # ページに貼る形

`--md` は `/daily-page` の入力にそのまま貼れる `- 定期起動: ...` の行を出す。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jst  # noqa: E402

#: 定期起動の一覧が入っていそうな鍵。版によって呼び方が違う
LIST_KEYS = ("data", "triggers", "items", "results")


def extract(raw: str | dict | list) -> list[dict]:
    """保存された結果から定期起動の一覧を取り出す。

    **見つからなければ止める。**空の一覧を返すと「定期起動は無し」と
    書かれたページができ、間違いに気づけない。
    """
    obj = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in LIST_KEYS:
            value = obj.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        raise ValueError(
            f"定期起動の一覧が見つからない。鍵は {sorted(obj)}。"
            f"探したのは {list(LIST_KEYS)}"
        )
    raise ValueError(f"読めない形: {type(obj).__name__}")


def has_more(raw: str | dict | list) -> bool:
    """保存された結果が**途中までか**を返す。

    `list_triggers` は 1 回で全部返さない(既定 20 件、最大 100 件)。
    途中までの一覧で数えると、**あるはずの定期起動が「無し」になる。**
    2026-10-06 に実際に 1 件取りこぼした(30 件の保存に 10-12 の分が入っていなかった)。
    """
    obj = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(obj, dict):
        return False
    return bool(obj.get("has_more") or obj.get("next_cursor"))


def for_session(triggers: list[dict], session_id: str) -> list[dict]:
    """そのセッションに紐づくものだけを、次に動く順で返す。"""
    mine = [t for t in triggers if t.get("persistent_session_id") == session_id]
    return sorted(mine, key=lambda t: str(t.get("next_run_at") or ""))


def when(trigger: dict) -> str:
    """次に動く時刻を日本時間の短い形で返す。無ければ空。"""
    raw = trigger.get("next_run_at") or trigger.get("run_once_at") or ""
    if not raw:
        return ""
    try:
        at = jst.parse(raw)
    except (ValueError, TypeError):
        return str(raw)
    if not isinstance(at, dt.datetime):
        return str(raw)
    return at.astimezone(jst.JST).strftime("%m-%d %H:%M")


def _title(trigger: dict) -> str:
    """名前から、プロジェクト名の接頭辞と末尾の省略記号を落とす。"""
    name = str(trigger.get("name") or "(名前なし)").strip()
    if ": " in name:
        name = name.split(": ", 1)[1]
    return name.rstrip("…").strip()


def lines(triggers: list[dict], *, md: bool = False) -> list[str]:
    """ページに貼る 1 行ずつ。`md` なら `- 定期起動: ` を付ける。"""
    out = []
    for t in triggers:
        w = when(t)
        body = f"{w} {_title(t)}".strip() if w else _title(t)
        if not t.get("enabled", True):
            body += "(止めてある)"
        out.append(f"- 定期起動: {body}" if md else body)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", help="保存された list_triggers の結果(JSON)")
    ap.add_argument("--session", required=True, help="セッション ID")
    ap.add_argument("--md", action="store_true", help="/daily-page に貼る形で出す")
    a = ap.parse_args(argv)

    try:
        raw = Path(a.path).read_text(encoding="utf-8")
        triggers = extract(raw)
    except (OSError, ValueError) as exc:
        print(f"できなかった: {exc}", file=sys.stderr)
        return 2
    if has_more(raw):
        print(
            f"※ この保存は途中まで({len(triggers)} 件)。"
            "list_triggers を next_cursor で続けて取り直さないと、"
            "**定期起動を取りこぼす**",
            file=sys.stderr,
        )
    mine = for_session(triggers, a.session)
    if not mine:
        print(
            f"このセッションに紐づく定期起動は無い(全体で {len(triggers)} 件)。"
            "セッション ID が合っているかを確かめる",
            file=sys.stderr,
        )
        return 1
    for line in lines(mine, md=a.md):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
