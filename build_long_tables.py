# build_long_tables.py
import json
from pathlib import Path
import pandas as pd
import numpy as np

def load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def extract_month_series(obj):
    """
    兼容常见 OpenDigger/OpenRank JSON 形式，返回 dict[month]=value
    支持：
    1) {"2020-01": 1, "2020-02": 2}
    2) {"data": {"2020-01": 1}}
    3) [{"date":"2020-01","value":1}, ...] / [{"month":"2020-01","value":1}, ...]
    4) {"2020-01": {"median": 3, "mean": 4}} -> 优先 median, 再 mean, 再 avg/value
    """
    if obj is None:
        return {}

    # case 2
    if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], (dict, list)):
        obj = obj["data"]

    # case 1 / 4
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and len(k) >= 7 and k[4] == "-":  # YYYY-MM
                out[k[:7]] = pick_scalar(v)
        return out

    # case 3
    if isinstance(obj, list):
        out = {}
        for it in obj:
            if not isinstance(it, dict):
                continue
            m = it.get("month") or it.get("date") or it.get("time") or it.get("key")
            if isinstance(m, str) and len(m) >= 7 and m[4] == "-":
                out[m[:7]] = pick_scalar(it.get("value", it.get("val", it.get("data"))))
        return out

    return {}

def pick_scalar(v):
    # v 可能是数字，也可能是 {median:..} 这种
    if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
        return float(v)
    if isinstance(v, dict):
        for key in ["median", "p50", "mean", "avg", "value"]:
            if key in v and isinstance(v[key], (int, float)):
                return float(v[key])
    return np.nan

def repo_iter(metrics_dir: Path):
    # 目录形如 top_300_metrics/org/repo/*.json
    for org_dir in metrics_dir.iterdir():
        if not org_dir.is_dir():
            continue
        for repo_dir in org_dir.iterdir():
            if repo_dir.is_dir():
                yield org_dir.name, repo_dir.name, repo_dir

def build_openrank_long(metrics_dir: Path):
    rows = []
    for org, repo, repo_dir in repo_iter(metrics_dir):
        p = repo_dir / "openrank.json"
        series = extract_month_series(load_json(p))
        for month, val in series.items():
            rows.append({
                "repo_full": f"{org}/{repo}",
                "org": org,
                "repo": repo,
                "month": month,
                "openrank": val
            })
    df = pd.DataFrame(rows)
    return df.sort_values(["repo_full", "month"]).reset_index(drop=True)

def build_ops_long(metrics_dir: Path, kind: str):
    """
    kind='issue' or 'pr'
    """
    if kind == "issue":
        files = {
            "issues_new": "issues_new.json",
            "issues_closed": "issues_closed.json",
            "issue_response_time": "issue_response_time.json",
            "issue_resolution_duration": "issue_resolution_duration.json",
        }
    else:
        files = {
            "change_requests": "change_requests.json",
            "change_request_response_time": "change_request_response_time.json",
            "change_request_resolution_duration": "change_request_resolution_duration.json",
        }

    rows = []
    for org, repo, repo_dir in repo_iter(metrics_dir):
        series_map = {}
        months = set()
        for col, fn in files.items():
            p = repo_dir / fn
            s = extract_month_series(load_json(p))
            series_map[col] = s
            months |= set(s.keys())

        for month in sorted(months):
            row = {"repo_full": f"{org}/{repo}", "org": org, "repo": repo, "month": month}
            for col in files.keys():
                row[col] = series_map[col].get(month, np.nan)
            rows.append(row)

    df = pd.DataFrame(rows)
    return df.sort_values(["repo_full", "month"]).reset_index(drop=True)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics_dir", required=True, help="top_300_metrics 解压后的目录")
    ap.add_argument("--out_dir", required=True, help="输出目录")
    args = ap.parse_args()

    metrics_dir = Path(args.metrics_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    openrank_long = build_openrank_long(metrics_dir)
    issue_ops = build_ops_long(metrics_dir, "issue")
    pr_ops = build_ops_long(metrics_dir, "pr")

    openrank_long.to_csv(out_dir / "openrank_long.csv", index=False, encoding="utf-8-sig")
    issue_ops.to_csv(out_dir / "issue_ops_long.csv", index=False, encoding="utf-8-sig")
    pr_ops.to_csv(out_dir / "pr_ops_long.csv", index=False, encoding="utf-8-sig")

    print("Done:")
    print(" -", out_dir / "openrank_long.csv")
    print(" -", out_dir / "issue_ops_long.csv")
    print(" -", out_dir / "pr_ops_long.csv")
