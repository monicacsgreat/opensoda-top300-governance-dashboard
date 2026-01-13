# build_long_tables.py
"""
Step 1：把 OpenDigger / OpenRank 的“每仓库一堆 JSON 文件”整理成 long table（长表/窄表）。

为什么要做 long 表？
- 原始结构：top_300_metrics/<org>/<repo>/*.json，每个指标一个 JSON，后续做 join / 计算比较麻烦
- long 表：每行 = (repo_full, month, 指标...)，非常适合做 groupby、merge、画图、建模

输入目录结构（期望）：
top_300_metrics/
  orgA/
    repo1/
      openrank.json
      issues_new.json
      issues_closed.json
      issue_response_time.json
      issue_resolution_duration.json
      change_requests.json
      change_request_response_time.json
      change_request_resolution_duration.json
    repo2/
      ...

输出（CSV）：
- openrank_long.csv：repo_full, org, repo, month, openrank
- issue_ops_long.csv：repo_full, org, repo, month, issues_new, issues_closed, issue_response_time, issue_resolution_duration
- pr_ops_long.csv：repo_full, org, repo, month, change_requests, change_request_response_time, change_request_resolution_duration

注：
- JSON 可能有不同形态（dict / list / 包一层 data），extract_month_series 会做兼容解析。
- 解析失败或缺失时用 NaN 填充，方便后续 pandas 计算。
"""
import json
from pathlib import Path
import pandas as pd
import numpy as np

def load_json(path: Path):
    """
    安全读取 JSON：
    - 成功返回 Python 对象（dict/list/number/...）
    - 失败（文件不存在/内容不合法/编码问题等）返回 None
    """
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

    # case 2:外面包一层 {"data": ...}
    if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], (dict, list)):
        obj = obj["data"]

    # case 1 / 4:dict 形态，key 直接是 "YYYY-MM"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and len(k) >= 7 and k[4] == "-":  # YYYY-MM
                out[k[:7]] = pick_scalar(v)
        return out

    # case 3:list of dict，每个元素带 month/date/value
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
    """
    从 JSON 的 value 中取一个可用的标量（float）。

    v 可能是：
    - 直接数字：1 / 1.23
    - 统计对象：{"median": 3, "mean": 4, ...}
    这里按优先级依次尝试：median -> p50 -> mean -> avg -> value
    """
    if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
        return float(v)
    if isinstance(v, dict):
        for key in ["median", "p50", "mean", "avg", "value"]:
            if key in v and isinstance(v[key], (int, float)):
                return float(v[key])
    return np.nan

def repo_iter(metrics_dir: Path):
    """
    遍历仓库目录：
    期望目录形如 top_300_metrics/org/repo/*.json

    yield: (org, repo, repo_dir_path)
    """
    # 目录形如 top_300_metrics/org/repo/*.json
    for org_dir in metrics_dir.iterdir():
        if not org_dir.is_dir():
            continue
        for repo_dir in org_dir.iterdir():
            if repo_dir.is_dir():
                yield org_dir.name, repo_dir.name, repo_dir

def build_openrank_long(metrics_dir: Path):
    """
    读取每个 repo 的 openrank.json 并展开为 long 表（每月一行）。
    """
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
    # 不同 kind 对应不同 JSON 文件集合
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
        series_map = {}# col -> dict[month]=value
        months = set()# 当前 repo 覆盖到的所有月份（做 union）
        # 逐个指标读 JSON，提取月序列
        for col, fn in files.items():
            p = repo_dir / fn
            s = extract_month_series(load_json(p))
            series_map[col] = s
            months |= set(s.keys())
         # 对每个月拼一行：缺失的指标用 NaN
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
    # 1) openrank long
    openrank_long = build_openrank_long(metrics_dir)
    # 2) issue / pr 运维 long
    issue_ops = build_ops_long(metrics_dir, "issue")
    pr_ops = build_ops_long(metrics_dir, "pr")
    # 输出为 CSV（utf-8-sig 方便 Excel）
    openrank_long.to_csv(out_dir / "openrank_long.csv", index=False, encoding="utf-8-sig")
    issue_ops.to_csv(out_dir / "issue_ops_long.csv", index=False, encoding="utf-8-sig")
    pr_ops.to_csv(out_dir / "pr_ops_long.csv", index=False, encoding="utf-8-sig")

    print("Done:")
    print(" -", out_dir / "openrank_long.csv")
    print(" -", out_dir / "issue_ops_long.csv")
    print(" -", out_dir / "pr_ops_long.csv")
