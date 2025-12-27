import json
from pathlib import Path
import argparse
import pandas as pd

import matplotlib
matplotlib.use("Agg")  
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]  
plt.rcParams["axes.unicode_minus"] = False


def series_to_long(repo: str, series, metric_name: str) -> pd.DataFrame:
    
    rows = []
    if isinstance(series, dict):
        for m, v in series.items():
            rows.append((repo, str(m), v))
    elif isinstance(series, list):
        for item in series:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                rows.append((repo, str(item[0]), item[1]))

    df = pd.DataFrame(rows, columns=["repo", "month", "value"])
    df["metric"] = metric_name
    return df


def load_metric(metrics_dir: Path, filename: str, metric_name: str) -> pd.DataFrame:
    
    root_file = metrics_dir / filename

    # A) 聚合格式
    if root_file.exists():
        with root_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        parts = []
        if isinstance(data, dict):
            for repo, series in data.items():
                df_repo = series_to_long(repo, series, metric_name)
                if not df_repo.empty:
                    parts.append(df_repo)
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["repo", "month", "value", "metric"])

    # B) 递归扫描
    files = list(metrics_dir.rglob(filename))
    if not files:
        return pd.DataFrame(columns=["repo", "month", "value", "metric"])

    parts = []
    for p in files:
        rel = p.relative_to(metrics_dir)
       
        if len(rel.parts) >= 3:
            repo = f"{rel.parts[0]}/{rel.parts[1]}"
        else:
            repo = str(p.parent.name)

        try:
            with p.open("r", encoding="utf-8") as f:
                series = json.load(f)
        except Exception:
            continue

        df_repo = series_to_long(repo, series, metric_name)
        if not df_repo.empty:
            parts.append(df_repo)

    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["repo", "month", "value", "metric"])


def norm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["month"] = df["month"].astype(str).str.slice(0, 7)  # YYYY-MM
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics_dir", default="top_300_metrics", help="top_300_metrics 解压后的目录")
    ap.add_argument("--start", default="2020-01", help="起始月份 YYYY-MM")
    ap.add_argument("--end", default="2023-03", help="结束月份 YYYY-MM")
    ap.add_argument("--out", default="out", help="输出目录")
    args = ap.parse_args()

    metrics_dir = Path(args.metrics_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    openrank = load_metric(metrics_dir, "openrank.json", "openrank")
    resp = load_metric(metrics_dir, "issue_response_time.json", "issue_response_time")

    if openrank.empty:
        raise SystemExit(
            "没加载到 openrank 数据。请确认：\n"
            f"1) --metrics_dir 指向 {metrics_dir.resolve()}\n"
            "2) 目录下确实存在 **/openrank.json"
        )

    openrank = norm(openrank)
    resp = norm(resp)

    # 时间范围筛选
    openrank = openrank[(openrank["month"] >= args.start) & (openrank["month"] <= args.end)]

    start_df = openrank[openrank["month"] == args.start][["repo", "value"]].rename(columns={"value": "start"})
    end_df = openrank[openrank["month"] == args.end][["repo", "value"]].rename(columns={"value": "end"})

    if start_df.empty:
        raise SystemExit(f"openrank 没有找到起始月份 {args.start} 的数据")
    if end_df.empty:
        raise SystemExit(f"openrank 没有找到结束月份 {args.end} 的数据")

    growth = start_df.merge(end_df, on="repo", how="inner")
    growth["delta"] = growth["end"] - growth["start"]
    top_growth = growth.sort_values("delta", ascending=False).head(15)

    # 图1：OpenRank 增长 TOP15
    plt.figure()
    plt.barh(top_growth["repo"][::-1], top_growth["delta"][::-1])
    plt.xlabel("OpenRank 增长（end - start）")
    plt.title(f"OpenRank 增长 TOP15（{args.start}→{args.end}）")
    plt.tight_layout()
    plt.savefig(str(out_dir / "openrank_top_growth.png"), dpi=180)
    plt.close()

    # 图2：OpenRank 期末 TOP15
    top_end = end_df.sort_values("end", ascending=False).head(15)
    plt.figure()
    plt.barh(top_end["repo"][::-1], top_end["end"][::-1])
    plt.xlabel(f"OpenRank（{args.end}）")
    plt.title(f"OpenRank TOP15（{args.end}）")
    plt.tight_layout()
    plt.savefig(str(out_dir / "openrank_top_end.png"), dpi=180)
    plt.close()

    # 散点图：影响力 vs 响应效率
    made_scatter = False
    if not resp.empty:
        resp_end = resp[resp["month"] == args.end][["repo", "value"]].rename(columns={"value": "resp_time"})
        if not resp_end.empty:
            scatter = end_df.merge(resp_end, on="repo", how="inner").dropna()
            if not scatter.empty:
                plt.figure()
                plt.scatter(scatter["end"], scatter["resp_time"])
                plt.xlabel(f"OpenRank（{args.end}）")
                plt.ylabel(f"Issue Response Time（{args.end}）")
                plt.title(f"影响力 vs 响应效率（{args.end}）")
                plt.tight_layout()
                plt.savefig(str(out_dir / "openrank_vs_response_time.png"), dpi=180)
                plt.close()
                scatter.sort_values(["end"], ascending=False).to_csv(
                    out_dir / "scatter_data.csv", index=False, encoding="utf-8-sig"
                )
                made_scatter = True

    # CSV 输出
    top_growth_rounded = top_growth.copy()
    for c in ["start", "end", "delta"]:
        top_growth_rounded[c] = top_growth_rounded[c].round(2)

    top_end_rounded = top_end.copy()
    top_end_rounded["end"] = top_end_rounded["end"].round(2)

    top_growth_rounded.to_csv(out_dir / "openrank_top_growth.csv", index=False, encoding="utf-8-sig")
    top_end_rounded.to_csv(out_dir / "openrank_top_end.csv", index=False, encoding="utf-8-sig")


    print(f"Done. 输出在：{out_dir.resolve()}")


if __name__ == "__main__":
    main()
