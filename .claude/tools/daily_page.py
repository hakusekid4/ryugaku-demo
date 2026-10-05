#!/usr/bin/env python3
"""各セッションの毎日のページ(HTML)を決まった形で作る(ai-config-review チケット 02)。

目的はセッションの題、実行内容はこのページで示す(2026-10-05 本人決定、grill #2〜#5)。
頭に「目的(題)」と「紐づく定期起動」、本体は 今日やったこと / 数字 / 次にやること /
本人に要ること の 4 欄。空の欄は「無し」と出す。出力は Artifact の決まりに合わせ、doctype・html・head・body を
含まない(公開時に外枠が付く)。<title> と <style> を先頭に置き、色は明暗両方の変数で持つ。**標準ライブラリだけで動く**(全リポジトリへ配る)。

    python .claude/tools/daily_page.py page.json -o page.html   # JSON から
    python .claude/tools/daily_page.py page.md -o page.html     # Markdown から
    python .claude/tools/daily_page.py --example                # 手本を標準出力へ

JSON の形: {"title", "date", "routines": [{"when", "what"} か文字列], "done", "numbers",
"next", "needs"}(4 欄は文字列か文字列の並び)。Markdown の形は `--example-md` で出る。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

SECTIONS = [("done", "今日やったこと"), ("numbers", "数字"), ("next", "次にやること"),
            ("needs", "本人に要ること")]

EXAMPLE = {
    "title": "ai-config: 開発の流れと仕組みの見直し",
    "date": "2026-10-06",
    "routines": [{"when": "毎晩 22:13", "what": "試し中のプロジェクトのチケットを 1 枚進める"}],
    "done": ["チケット 01「作業フィードをやめる」を done にした"],
    "numbers": ["今週のチケット: 片付いた 5 枚 / 止まった 0 枚"],
    "next": ["チケット 03「見取り図がセッション一覧を全ページ読む」"],
    "needs": [],
}

EXAMPLE_MD = """# ai-config: 開発の流れと仕組みの見直し

- 日付: 2026-10-06
- 定期起動: 毎晩 22:13 試し中のプロジェクトのチケットを 1 枚進める

## 今日やったこと
- チケット 01「作業フィードをやめる」を done にした

## 数字
- 今週のチケット: 片付いた 5 枚 / 止まった 0 枚

## 次にやること
- チケット 03「見取り図がセッション一覧を全ページ読む」

## 本人に要ること
"""

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--accent:#2f6fde;--warn:#b5471b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151517;--card:#1f1f22;--fg:#ececee;--muted:#9a9aa1;--line:#2e2e33;--accent:#7aa7ff;--warn:#ff9a6b;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#151517;--card:#1f1f22;--fg:#ececee;--muted:#9a9aa1;--line:#2e2e33;--accent:#7aa7ff;--warn:#ff9a6b;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 48px}
header{border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:20px}
h1{font-size:1.35rem;margin:0 0 4px;overflow-wrap:anywhere}
.date{color:var(--muted);font-size:.9rem}
.routines{margin:12px 0 0;padding:0;list-style:none;font-size:.92rem}
.routines li{color:var(--muted)}
.routines b{color:var(--fg);font-weight:600}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 14px}
h2{font-size:1rem;margin:0 0 6px;color:var(--accent)}
section.needs h2{color:var(--warn)}
ul{margin:0;padding-left:1.2em}
li{overflow-wrap:anywhere}
.none{color:var(--muted);margin:0}
"""


def _items(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    return [str(x) for x in v if str(x).strip()]


def _routine(r) -> str:
    if isinstance(r, dict):
        when, what = r.get("when", ""), r.get("what", "")
        return f"<b>{html.escape(str(when))}</b> {html.escape(str(what))}".strip()
    return html.escape(str(r))


def render(data: dict) -> str:
    """入力(辞書)→ HTML の文字列。題が無ければ ValueError。"""
    title = str(data.get("title") or "").strip()
    if not title:
        raise ValueError("題(title)が無い。目的はセッションの題で示す決まり")
    esc = html.escape
    routines = data.get("routines") or []
    if isinstance(routines, (str, dict)):
        routines = [routines]
    if routines:
        rt = "".join(f"<li>{_routine(r)}</li>" for r in routines)
    else:
        rt = "<li>無し</li>"
    parts = [
        f"<title>{esc(title)}</title>",
        f"<style>{CSS}</style>",
        '<main lang="ja">',
        "<header>",
        f"<h1>{esc(title)}</h1>",
        f'<div class="date">{esc(str(data.get("date") or ""))} 時点</div>',
        f'<ul class="routines"><li><b>定期起動</b></li>{rt}</ul>',
        "</header>",
    ]
    for key, label in SECTIONS:
        items = _items(data.get(key))
        body = ("<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>") if items \
            else '<p class="none">無し</p>'
        parts.append(f'<section class="{key}"><h2>{label}</h2>{body}</section>')
    parts.append("</main>")
    return "\n".join(parts) + "\n"


def parse_markdown(md: str) -> dict:
    """`# 題` / `- 日付:` / `- 定期起動:`(複数可)/ `## <欄の名前>` の下の `- 項目` を読む。"""
    data: dict = {"title": "", "date": "", "routines": [], **{k: [] for k, _ in SECTIONS}}
    label_to_key = {label: key for key, label in SECTIONS}
    cur = None
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("# ") and not data["title"]:
            data["title"] = s[2:].strip()
            continue
        if s.startswith("## "):
            cur = label_to_key.get(s[3:].strip())
            continue
        m = re.match(r"^[-*]\s+(.*)$", s)
        if not m:
            continue
        item = m.group(1).strip()
        if cur is None:
            if item.startswith("日付:"):
                data["date"] = item.split(":", 1)[1].strip()
            elif item.startswith("定期起動:"):
                data["routines"].append(item.split(":", 1)[1].strip())
        elif item:
            data[cur].append(item)
    return data


def load(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return parse_markdown(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", nargs="?", help="JSON か Markdown のファイル")
    ap.add_argument("-o", "--out", help="書き出す HTML のパス(省略で標準出力)")
    ap.add_argument("--example", action="store_true", help="手本の HTML を出す")
    ap.add_argument("--example-md", action="store_true", help="入力の Markdown の手本を出す")
    a = ap.parse_args(argv)
    if a.example_md:
        sys.stdout.write(EXAMPLE_MD)
        return 0
    if a.example:
        data = EXAMPLE
    elif a.input:
        data = load(Path(a.input))
    else:
        ap.error("入力のファイルか --example を渡す")
    try:
        out = render(data)
    except ValueError as e:
        print(f"daily_page: {e}", file=sys.stderr)
        return 1
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
