#!/usr/bin/env python3
"""時刻を日本時間(JST)でそろえるための小さな部品。2026-09-20 本人指示。

なぜ要るか:

 - クラウド(GitHub Actions・Claude Code のセッション)の時計は UTC で動く。
   そのまま `date.today()` を呼ぶと、日本の朝 9 時より前は**前の日**が返る。
   「生成日: 2026-09-19」と書かれた設定が 9-20 の朝に配られる、といった食い違いが起きる
 - 記録(JSON・JSONL)にも UTC の `...Z` と日本時間が混ざると、後から読むときに
   9 時間ずれたまま並べてしまう

決め: **このリポジトリが書き出す時刻は、機械が読むものも人が読むものも、すべて日本時間。**

  - 機械が読む欄(JSON の `generatedAt` など): `2026-09-20T21:00:00+09:00`
    (`+09:00` が付いているので、UTC の `...Z` と混ざっても機械は取り違えない)
  - 人が読む文章・表: `2026-09-20 21:00`(必要なら末尾に `JST`)

読むときは `parse()` を使う。`...Z` でも `+09:00` でも、時間帯の付いていない文字列でも
受け取れる(付いていないものは日本時間とみなす)。過去の記録に残っている UTC の行は
書き換えない(`errors/log.jsonl` は追記専用のため)。読むときに揃えれば足りる。
"""
from __future__ import annotations

import datetime as dt

#: 日本標準時(UTC より 9 時間進んでいる。夏時間は無い)
JST = dt.timezone(dt.timedelta(hours=9), "JST")

#: 機械が読む時刻の形(例 `2026-09-20T21:00:00+09:00`)
ISO = "%Y-%m-%dT%H:%M:%S%z"


def now() -> dt.datetime:
    """今の日本時間(時間帯つき)。"""
    return dt.datetime.now(JST)


def today() -> dt.date:
    """日本時間での今日の日付。`date.today()` の代わりに使う。"""
    return now().date()


def to_jst(when: dt.datetime) -> dt.datetime:
    """どの時間帯の日時でも日本時間に直す。時間帯が無いものは日本時間とみなす。"""
    if when.tzinfo is None:
        return when.replace(tzinfo=JST)
    return when.astimezone(JST)


def stamp(when: dt.datetime | None = None) -> str:
    """機械が読む時刻の文字列(`2026-09-20T21:00:00+09:00`)を返す。"""
    return to_jst(when or now()).strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0900", "+09:00")


def fmt(when: dt.datetime | str | None = None, *, zone: bool = False,
        shape: str = "%Y-%m-%d %H:%M") -> str:
    """人が読む時刻の文字列(`2026-09-20 21:00`)を返す。

    `zone=True` で末尾に ` JST` を付ける(UTC の記録と並べて出すときなど、
    どちらの時刻か紛れる場所ではこちらを使う)。
    """
    if isinstance(when, str):
        parsed = parse(when)
        if parsed is None:
            return when          # 読めない文字列はそのまま返す(表が崩れないように)
        when = parsed
    text = to_jst(when or now()).strftime(shape)
    return f"{text} JST" if zone else text


def parse(text: str) -> dt.datetime | None:
    """時刻の文字列を日本時間の日時にする。読めなければ None。

    受け取れる形: `2026-09-20T12:00:00Z`(UTC)、`2026-09-20T21:00:00+09:00`、
    `2026-09-20 21:00:00`(時間帯なし = 日本時間とみなす)、`2026-09-20`。
    """
    if not isinstance(text, str) or not text.strip():
        return None
    raw = text.strip().replace("Z", "+00:00").replace("z", "+00:00")
    try:
        return to_jst(dt.datetime.fromisoformat(raw))
    except ValueError:
        return None


def sort_key(text: str) -> str:
    """時刻の文字列を「並べ替えの鍵」にする。

    古い記録の UTC(`...Z`)と、これから書く日本時間(`+09:00`)が混ざっていても、
    同じ物差しで並ぶようにするためのもの。読めない文字列はそのまま鍵にする
    (並び順は崩れるが、落とさない)。
    """
    when = parse(text)
    return when.strftime("%Y-%m-%dT%H:%M:%S") if when else str(text)
