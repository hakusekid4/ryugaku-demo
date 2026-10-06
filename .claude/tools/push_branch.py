#!/usr/bin/env python3
"""押す。跳ねられたら取り込んで押し直す。**力技(--force)は使わない。**

**なぜ要るか**(2026-10-06): `git push` が「fetch first」で跳ねられる形は、
別セッションや自動同期が先に押していれば普通に起きる。そのとき決まり文句の
retry ループ(`for i in 1 2 3 4; do git push ...`)は**同じ push を 4 回繰り返すだけ**で、
一度も通らないまま 30 秒を捨てる。retry が効くのは通信の失敗のときだけ。

今日 `paddock-video-ai` で 2 回踏んだ。どちらも手で
`git fetch` → `git rebase origin/main` → 試験 → `git push` を打ち直した。
同じ形は `keiba_rl_sim_digest_commit.py`(AUT-A235)と V4 の実験ループ(AUT-A44)でも
踏んでいて、そのたびに別々に直している。ここに寄せる。

    python scripts/push_branch.py
    python scripts/push_branch.py --test "python -m unittest discover -s tests"
    python scripts/push_branch.py --branch main --remote origin

やること:

1. 先に `git fetch`。**押してから跳ねられるのを待たない**
2. 遠くに自分の知らないコミットがあれば `git rebase`(**押していないコミットだけが動く**)
3. `--test` があれば、取り込んだあとに走らせる。落ちたら押さない
4. `git push`。通信の失敗だけ 2・4・8・16 秒で retry

**押し済みの履歴は書き換えない。**`--force` は付けないので、
書き換えが要る形なら push が跳ねたまま終わる(終了コード 1)。
ai-config 自身は `sync_branch.py`(作業ブランチ → main)を使う。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

#: 通信の失敗と見なす文字列。これが出たときだけ同じ push を retry する
NETWORK_HINTS = (
    "could not resolve host", "connection reset", "connection timed out",
    "rpc failed", "unexpected disconnect", "early eof", "operation timed out",
    "failed to connect", "ssl_read", "the remote end hung up",
)

#: 「先に取り込め」と言われた形。retry ではなく rebase で直す
BEHIND_HINTS = ("fetch first", "non-fast-forward", "rejected")

#: 通信の失敗で待つ秒数
BACKOFF = (2, 4, 8, 16)


def git(*args: str, cwd: str | None = None) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def _has(text: str, hints: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(h in low for h in hints)


def current_branch(cwd: str | None = None) -> str:
    code, out = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return out.strip() if code == 0 else ""


def behind(remote: str, branch: str, cwd: str | None = None) -> int:
    """遠くにあって手元に無いコミットの数。"""
    code, out = git("rev-list", "--count", f"HEAD..{remote}/{branch}", cwd=cwd)
    return int(out.strip()) if code == 0 and out.strip().isdigit() else 0


def ahead(remote: str, branch: str, cwd: str | None = None) -> int:
    """手元にあって遠くに無い(= まだ押していない)コミットの数。"""
    code, out = git("rev-list", "--count", f"{remote}/{branch}..HEAD", cwd=cwd)
    return int(out.strip()) if code == 0 and out.strip().isdigit() else 0


def take_in(remote: str, branch: str, cwd: str | None = None) -> tuple[bool, str]:
    """遠くの分を取り込む。失敗したら rebase を取り消して理由を返す。"""
    code, out = git("rebase", f"{remote}/{branch}", cwd=cwd)
    if code == 0:
        return True, out
    git("rebase", "--abort", cwd=cwd)
    return False, out


def run_test(command: str, cwd: str | None = None) -> tuple[bool, str]:
    p = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr)


def push(
    remote: str = "origin", branch: str = "", *, test: str = "",
    cwd: str | None = None, sleep=time.sleep,
) -> int:
    branch = branch or current_branch(cwd)
    if not branch or branch == "HEAD":
        print("いまのブランチが分からない(detached HEAD)。--branch で渡す", file=sys.stderr)
        return 2

    code, out = git("fetch", remote, branch, cwd=cwd)
    if code != 0:
        print(f"fetch できなかった: {out.strip()}", file=sys.stderr)
        if not _has(out, NETWORK_HINTS):
            return 2

    if behind(remote, branch, cwd=cwd):
        n = behind(remote, branch, cwd=cwd)
        print(f"{remote}/{branch} に自分の知らないコミットが {n} 件。取り込む")
        ok, out = take_in(remote, branch, cwd=cwd)
        if not ok:
            print("取り込めなかった(ぶつかっている)。手で直す:", file=sys.stderr)
            print(out.strip()[-800:], file=sys.stderr)
            return 1
        if test:
            print(f"取り込んだので試験を走らせる: {test}")
            ok, out = run_test(test, cwd=cwd)
            if not ok:
                print("取り込んだあとで試験が落ちた。押さない:", file=sys.stderr)
                print(out.strip()[-800:], file=sys.stderr)
                return 1
            print("試験は通った")

    if not ahead(remote, branch, cwd=cwd):
        print(f"押すものが無い({remote}/{branch} と同じ)")
        return 0

    for i, wait in enumerate((0, *BACKOFF)):
        if wait:
            sleep(wait)
        code, out = git("push", "-u", remote, branch, cwd=cwd)
        if code == 0:
            print(f"押した: {remote}/{branch}")
            return 0
        if _has(out, NETWORK_HINTS):
            print(f"通信で失敗。{BACKOFF[i] if i < len(BACKOFF) else 0} 秒待って retry")
            continue
        if _has(out, BEHIND_HINTS):
            print("また先を越された。もう一度このコマンドを実行する", file=sys.stderr)
            print(out.strip()[-400:], file=sys.stderr)
            return 1
        print(f"押せなかった: {out.strip()[-800:]}", file=sys.stderr)
        return 1
    print("通信の失敗が続いた。あとでもう一度", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default="", help="省略でいまのブランチ")
    ap.add_argument("--test", default="", help="取り込んだあとに走らせるコマンド")
    a = ap.parse_args(argv)
    return push(a.remote, a.branch, test=a.test)


if __name__ == "__main__":
    raise SystemExit(main())
