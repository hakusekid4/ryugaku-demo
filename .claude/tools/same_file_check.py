#!/usr/bin/env python3
"""司令塔の「同じファイルを触った」連絡を、機械で確かめる(2026-09-24)。

**なぜ要るか**: 司令塔(`keibaAI-V4:scripts/conductor.py`)は 24 時間以内に
複数のセッションが触ったファイルを名指しして「`git pull` してから、相手の変更を
消していないか・同じものを二重に作っていないか確かめて」と連絡してくる。
**その確かめ方は毎回まったく同じ手順**なのに、毎回その場で組み立てていた ——
2026-09-24 だけで 2 回(`pc/run.ps1` と `tests/test_racedata.py`)、
`git log origin/main -- <file>` を叩き、`git show origin/main:<file>` を grep して
「自分の足したものが残っているか」を目で見ていた。

**手で見ると取りこぼす形が 1 つある**: 手元が `origin/main` より遅れているとき、
その古い写しを push すると**相手の変更を消す**。遅れは連絡に書かれていないので、
ファイルの中身だけを見ていると気づけない。

    python scripts/same_file_check.py keibaai-v4:tests/test_racedata.py pc/run.ps1
    python scripts/same_file_check.py --no-fetch <ファイル>...
    python scripts/same_file_check.py --root keibaai-v4=/path/to/clone <ファイル>...

連絡の書き方(`<リポジトリ>:<パス>`)をそのまま貼れる。`:` が無ければこのリポジトリ。

終了コード: 0 = どのファイルも安全 / 1 = 手を打つものがある。
**「相手の変更を消したか」そのものは判定しない**(中身の意味は機械には分からない)。
分かるのは「消しうる状態か」「自分のものが `origin/main` に残っているか」まで。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: `<リポジトリ>:<パス>` の左側から場所を引くときの既定。
DEFAULT_ROOTS = {
    "ai-config": ROOT,
    "keibaai-v4": Path("/home/user/keibaai-v4"),
    "keibaai-v3-next": Path("/home/user/keibaai-v3-next"),
    "keibaai-llm": Path("/home/user/keibaai-llm"),
}


def git(repo: Path, *args: str) -> tuple[int, str]:
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    return out.returncode, out.stdout.strip()


def split_target(target: str, roots: dict[str, Path]) -> tuple[Path, str]:
    """`keibaai-v4:tests/x.py` を (場所, パス) にする。`:` が無ければこのリポジトリ。"""
    name, sep, path = target.partition(":")
    if not sep:
        return roots.get("ai-config", ROOT), target
    key = name.strip().lower()
    if key not in roots:
        raise KeyError(name)
    return roots[key], path.strip()


def check_file(repo: Path, rel: str, ref: str = "origin/main") -> dict:
    """1 ファイルぶんの見立て。**判断はせず、材料だけ集める。**"""
    info: dict = {"repo": repo.name, "path": rel, "notes": [], "act": False}

    if git(repo, "rev-parse", "--git-dir")[0] != 0:
        info["notes"].append(f"{repo} は git の作業場ではない")
        info["act"] = True
        return info
    if git(repo, "rev-parse", "--verify", "-q", ref)[0] != 0:
        info["notes"].append(f"{ref} が手元に無い(先に git fetch)")
        info["act"] = True
        return info

    # 手元にだけある変更(まだコミットしていない)
    _, dirty = git(repo, "status", "--porcelain", "--", rel)
    if dirty:
        info["notes"].append("手元にコミットしていない変更がある")
        info["act"] = True

    # 自分にしか無いコミット / 向こうにしか無いコミット(このファイルに限る)
    _, ahead = git(repo, "log", "--oneline", f"{ref}..HEAD", "--", rel)
    _, behind = git(repo, "log", "--oneline", f"HEAD..{ref}", "--", rel)
    info["ahead"] = [l for l in ahead.splitlines() if l.strip()]
    info["behind"] = [l for l in behind.splitlines() if l.strip()]

    if info["behind"]:
        # ここが手で見ていて落としやすいところ。中身だけ見ても気づけない。
        info["notes"].append(
            f"**{ref} に自分の知らない変更が {len(info['behind'])} 件**。"
            "このまま push すると相手の変更を消す。先に取り込む")
        info["act"] = True
    if info["ahead"]:
        info["notes"].append(f"自分の変更 {len(info['ahead'])} 件がまだ {ref} に無い")
        info["act"] = True

    # 中身がそろっているか(遅れも進みも無ければ、見るべきものは無い)
    _, diff = git(repo, "diff", "--stat", ref, "--", rel)
    info["same"] = not diff
    if info["same"] and not info["ahead"] and not info["behind"]:
        info["notes"].append(f"{ref} と同じ中身。消し合いは起きていない")

    _, last = git(repo, "log", "-1", "--format=%h %ad %s", "--date=format:%m-%d %H:%M",
                  ref, "--", rel)
    info["last"] = last
    _, touched = git(repo, "log", "--format=%h", f"--since=48 hours ago", ref, "--", rel)
    info["recent"] = len([l for l in touched.splitlines() if l.strip()])
    return info


def render(results: list[dict], ref: str = "origin/main") -> str:
    out = ["# 同じファイルを触った連絡の確認", ""]
    for r in results:
        out.append(f"## {r['repo']}:{r['path']}")
        if r.get("last"):
            out.append(f"- {ref} の最後の変更: {r['last']}")
        if r.get("recent"):
            out.append(f"- 48 時間以内に {r['recent']} 件の変更が入っている")
        for n in r["notes"]:
            out.append(f"- {n}")
        for line in r.get("behind", []):
            out.append(f"    [取り込む] {line}")
        for line in r.get("ahead", []):
            out.append(f"    [押す]     {line}")
        out.append("")
    if any(r["act"] for r in results):
        out.append("**手を打つものがある。**上の [取り込む] を先に、そのあと [押す]。")
    else:
        out.append("**どれも安全。**返事は要らない(司令塔の連絡は返信不要)。")
    out.append("")
    out.append("**中身の意味までは見ていない。**「相手の変更を消したか」は、"
               "上の差分を自分の目で読むこと。")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="+", help="`<リポジトリ>:<パス>` か、ただのパス")
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--no-fetch", action="store_true", help="fetch を省く(offline)")
    ap.add_argument("--root", action="append", default=[],
                    metavar="名前=場所", help="場所の割り当てを足す・上書きする")
    args = ap.parse_args(argv[1:])

    roots = dict(DEFAULT_ROOTS)
    for pair in args.root:
        name, _, path = pair.partition("=")
        roots[name.strip().lower()] = Path(path.strip())

    remote, _, branch = args.ref.partition("/")
    fetched: set[Path] = set()
    results = []
    for target in args.targets:
        try:
            repo, rel = split_target(target, roots)
        except KeyError as exc:
            print(f"知らないリポジトリ: {exc}。--root 名前=場所 で教えること", file=sys.stderr)
            return 2
        if not args.no_fetch and repo not in fetched:
            fetched.add(repo)
            # コロン付きの refspec。これが無いと FETCH_HEAD しか更新されない
            # (2026-09-22、next_id.py が古い ref を読んで番号を 4 回ぶつけた)。
            git(repo, "fetch", "-q", remote, f"{branch}:refs/remotes/{args.ref}")
        results.append(check_file(repo, rel, args.ref))

    print(render(results, args.ref))
    return 1 if any(r["act"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
