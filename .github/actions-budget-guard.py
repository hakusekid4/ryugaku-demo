"""そのリポジトリが当月に使った GitHub Actions の分数を数え、持ち分を超えていたら止める。

**なぜ「リポジトリまるごと」なのか(2026-09-22、2 度目の失敗を受けて)。**

1 度目(2026-09-21): `experiment-loop.yml` の `timeout-minutes` と `--budget-seconds` を
実測に合わせた。**1 回の長さ**しか縛っておらず、回数が青天井だった。

2 度目(2026-09-22): 回数の上限を足した。ただし **`experiment-loop` 1 本だけ**だった。
実測すると、9 月の課金 3,507 分のうちその関門が見ていたのは **1,059 分(30%)**。
残り 2,448 分(70%)は素通りで、同じ日に枠が尽きた。

    keibaAI-V4 / experiment-loop   1,059 分  ← 関門あり
    keibaAI-V4 / smoke               577 分  ← 素通り
    keibaAI-V4 / test                544 分  ← 素通り
    keibaAI-V3-next / ci             315 分  ← 素通り
    ai-config / sync-ai-config       250 分  ← 素通り
    FXandKABU / ci                   228 分  ← 素通り
    ai-config / test                 215 分  ← 素通り
      ...

**どちらも「一部だけを縛って、全体を縛ったつもりになった」という同じ間違い。**
だからこの歯止めは、ワークフローを名指ししない。**そのリポジトリの全実行**を数える。

**新しい権限は要らない。**ワークフローに自動で入る `GITHUB_TOKEN` は、
自分のリポジトリの Actions を読める。他リポジトリを見ようとすると個人トークンに
`Actions: Read` を足す必要があり、**本人の手が要る = その手が入るまで歯止めが
効かない**(しかも黙って 0 件を返す)。それを避けるため、各リポジトリが自分の
持ち分だけを見る形にした。持ち分の合計が無料枠(月 2,000 分)に収まっていれば、
口座全体も収まる。

使い方(ワークフローのいちばん最初のステップ、pip を入れる前):

    python .github/actions-budget-guard.py --max-minutes-per-month 700

終了コード:

    0  走ってよい
    3  持ち分を超えている。**これは失敗ではない。**呼ぶ側はワークフローを
       赤くせず、その回を何もせずに終わらせる
    1  本物の失敗(gh が無い・応答が読めない)。**通さずに止める。**
       通すと歯止めが「あるように見えて何もしていない」状態になる

数え方は GitHub の請求に合わせて **1 実行ごとに 1 分単位で切り上げ**る。
1 実行 1 ジョブとみなすので、多めに見て早めに止まる側に倒してある。
"""
import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

# 取りに行く件数。9 月の実測でいちばん多いリポジトリが月 1,100 実行だったので、
# 2,000 あれば当月は入りきる。入りきらないと**少なく数えて通してしまう**ので、
# 取れた最古の実行が当月の初めより後なら警告を出す(下の check_coverage)。
FETCH_LIMIT = 2000

GO = 0
ERROR = 1
STOP = 3


def parse_time(text: str) -> datetime:
    """GitHub が返す時刻(UTC)を日本時間へ直す。"""
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(JST)


def billable_minutes(run: dict, now: datetime) -> int:
    """1 実行が使った分数。**GitHub と同じく 1 分単位で切り上げる。**

    20 秒で終わった実行も 1 分として請求される。だから**回数の多さがそのまま効く。**
    実測では ai-config の `test` が 215 実行で 215 分(全部が最低単位)だった。

    まだ走っている実行は、いまこの瞬間までを使ったものとして数える。
    走り終わるのを待つと、走っている最中の暴走を止められない。
    """
    start = parse_time(run.get("startedAt") or run["createdAt"])
    if run.get("status") == "completed" and run.get("updatedAt"):
        end = parse_time(run["updatedAt"])
    else:
        end = now
    return max(1, math.ceil(max(0.0, (end - start).total_seconds()) / 60))


def fetch_runs(limit: int = FETCH_LIMIT, workflow: str | None = None) -> list[dict]:
    """`gh` で、このリポジトリの実行履歴を取る。ワークフローは名指ししない。"""
    cmd = ["gh", "run", "list", "--limit", str(limit),
           "--json", "databaseId,createdAt,startedAt,updatedAt,status,workflowName"]
    if workflow:
        cmd[3:3] = ["--workflow", workflow]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        # **`gh` の言い分をそのまま持ち上げる**(2026-09-25)。
        # `check=True` の例外には stderr が入らないので、これまでは
        # 「returned non-zero exit status 1」しか残らず、原因が読めなかった。
        # 実際の詰まりは権限(`actions: read` が無い)で、**そう書いてあれば
        # 15 回赤くなる前に気づけた。**
        raise RuntimeError(
            f"gh が失敗した(終了コード {out.returncode})。"
            f"{(out.stderr or out.stdout).strip()[:400]}\n"
            "  よくある原因: ワークフローの `permissions:` に `actions: read` が無い"
            "(**書かなかった権限は none になる**)")
    return json.loads(out.stdout)


def month_of(dt: datetime) -> tuple[int, int]:
    return (dt.year, dt.month)


def check_coverage(runs: list[dict], now: datetime, limit: int) -> str:
    """**取りこぼしの見張り。**

    `--limit` で切られて当月の初めまで届いていないと、少なく数えて通してしまう。
    履歴の件数が上限ちょうどで、かついちばん古い実行が当月に入っていたら、
    その先にまだ当月の実行が眠っている。
    """
    if len(runs) < limit:
        return ""
    oldest = min(parse_time(r["createdAt"]) for r in runs)
    if month_of(oldest) == month_of(now):
        return (f"履歴が {limit} 件で頭打ちになり、当月の初めまで届いていない"
                f"(いちばん古いのが {oldest:%Y-%m-%d})。数え落としがある")
    return ""


def decide(runs: list[dict], now: datetime, self_id: int | None,
           max_minutes_per_month: int,
           max_per_day: int = 0, workflow: str | None = None) -> tuple[int, str]:
    """走ってよいかを決める。戻り値は (終了コード, 説明)。

    **自分自身は数に入れない。**この歯止めは自分が走り出したあとに動くので、
    自分を数えると上限 1 のときに永久に走れなくなる。

    **自分より後にできた実行も数えない。**本番では gh が「いま存在するもの」しか
    返さないので自明だが、過去を再生して確かめるときに効く。
    """
    others = [r for r in runs
              if r.get("databaseId") != self_id and parse_time(r["createdAt"]) <= now]

    if max_per_day and workflow:
        today = now.date()
        same = [r for r in others
                if r.get("workflowName") == workflow
                and parse_time(r["createdAt"]).date() == today]
        if len(same) >= max_per_day:
            return STOP, (f"{workflow} は今日({today})すでに {len(same)} 回走っている"
                          f"(上限 {max_per_day} 回)。この回は何もせずに終わる")

    this_month = [r for r in others if month_of(parse_time(r["createdAt"])) == month_of(now)]
    used = sum(billable_minutes(r, now) for r in this_month)
    if used >= max_minutes_per_month:
        top = {}
        for r in this_month:
            name = r.get("workflowName") or "?"
            top[name] = top.get(name, 0) + billable_minutes(r, now)
        breakdown = "、".join(f"{k} {v} 分" for k, v in
                             sorted(top.items(), key=lambda x: -x[1])[:3])
        return STOP, (f"このリポジトリは {now.year}-{now.month:02d} にすでに {used} 分使っている"
                      f"(持ち分 {max_minutes_per_month} 分)。内訳の上位: {breakdown}。"
                      "この回は何もせずに終わる")

    return GO, (f"走ってよい。このリポジトリの当月 {used} / {max_minutes_per_month} 分"
                f"({len(this_month)} 実行)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-minutes-per-month", type=int, required=True,
                    help="このリポジトリが当月に使ってよい分数(全ワークフローの合計)")
    ap.add_argument("--max-per-day", type=int, default=0,
                    help="--workflow と併せて使う。そのワークフローの 1 日の回数の上限")
    ap.add_argument("--workflow", default=None,
                    help="--max-per-day の対象にするワークフロー名(表示名)")
    ap.add_argument("--self-id", type=int,
                    default=int(os.environ["GITHUB_RUN_ID"]) if os.environ.get("GITHUB_RUN_ID") else None,
                    help="この実行の run id。既定は $GITHUB_RUN_ID。数から除く")
    ap.add_argument("--limit", type=int, default=FETCH_LIMIT)
    ap.add_argument("--runs-json", type=Path, default=None,
                    help="試験用。gh を呼ばず、このファイルの JSON を履歴として使う")
    ap.add_argument("--now", default=None, help="試験用。この時刻を「いま」とみなす")
    args = ap.parse_args()

    now = (datetime.now(JST) if args.now is None
           else datetime.fromisoformat(args.now).astimezone(JST))

    try:
        if args.runs_json is not None:
            runs = json.loads(args.runs_json.read_text(encoding="utf-8"))
        else:
            runs = fetch_runs(args.limit)
    except Exception as e:  # noqa: BLE001
        # **黙って通さない。**通すと「あるように見えて何もしていない」状態になる
        # —— これまで 2 回とも、そういう形で気づくのが遅れた。
        print(f"実行履歴を読めなかったので止める: {e}", file=sys.stderr)
        return ERROR

    warn = check_coverage(runs, now, args.limit)
    if warn:
        print(f"::warning::{warn}")

    code, why = decide(runs, now, args.self_id, args.max_minutes_per_month,
                       args.max_per_day, args.workflow)
    print(why)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
