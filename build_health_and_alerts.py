# build_health_and_alerts.py
import pandas as pd
import numpy as np
from pathlib import Path

def percentile_rank(s: pd.Series, higher_is_better=True):
    # 用分位数/排名做归一化，抗极端值
    s2 = s.copy()
    if not higher_is_better:
        s2 = -s2
    # rank(pct=True) 会自动忽略 NaN
    return s2.rank(pct=True)

def health_level(score):
    if score >= 70:
        return "绿"
    if score >= 45:
        return "黄"
    return "红"

def build_end_snapshot(openrank_long, issue_ops_long, pr_ops_long, end_month: str, start_month: str):
    # 期末值
    end_or = openrank_long[openrank_long["month"] == end_month][["repo_full","openrank"]].rename(columns={"openrank":"openrank_end"})
    st_or = openrank_long[openrank_long["month"] == start_month][["repo_full","openrank"]].rename(columns={"openrank":"openrank_start"})
    snap = end_or.merge(st_or, on="repo_full", how="left")
    snap["openrank_delta"] = snap["openrank_end"] - snap["openrank_start"]

    # Issue 期末
    iss_end = issue_ops_long[issue_ops_long["month"] == end_month][
        ["repo_full","issues_new","issues_closed","issue_response_time","issue_resolution_duration"]
    ].copy()
    iss_end["backlog_end"] = iss_end["issues_new"] - iss_end["issues_closed"]
    iss_end = iss_end.drop(columns=["issues_new","issues_closed"])

    # PR 期末
    pr_end = pr_ops_long[pr_ops_long["month"] == end_month][
        ["repo_full","change_requests","change_request_response_time","change_request_resolution_duration"]
    ].copy()

    snap = snap.merge(iss_end, on="repo_full", how="left").merge(pr_end, on="repo_full", how="left")
    return snap

def compute_health_score(snap: pd.DataFrame):
    
    w = {
        "openrank_end": 0.35,
        "openrank_delta": 0.20,
        "issue_response_time": 0.15,
        "backlog_end": 0.10,
        "issue_resolution_duration": 0.10,
        "change_request_response_time": 0.05,
        "change_request_resolution_duration": 0.05,
    }

    s = snap.copy()

    # 归一化（分位数）
    s["n_openrank_end"] = percentile_rank(s["openrank_end"], True)
    s["n_openrank_delta"] = percentile_rank(s["openrank_delta"], True)

    # 越小越好
    s["n_issue_response_time"] = percentile_rank(s["issue_response_time"], False)
    s["n_backlog_end"] = percentile_rank(s["backlog_end"], False)
    s["n_issue_resolution_duration"] = percentile_rank(s["issue_resolution_duration"], False)
    s["n_pr_response_time"] = percentile_rank(s["change_request_response_time"], False)
    s["n_pr_resolution_duration"] = percentile_rank(s["change_request_resolution_duration"], False)

    # 加权得分（0~100）
    score = (
        w["openrank_end"] * s["n_openrank_end"] +
        w["openrank_delta"] * s["n_openrank_delta"] +
        w["issue_response_time"] * s["n_issue_response_time"] +
        w["backlog_end"] * s["n_backlog_end"] +
        w["issue_resolution_duration"] * s["n_issue_resolution_duration"] +
        w["change_request_response_time"] * s["n_pr_response_time"] +
        w["change_request_resolution_duration"] * s["n_pr_resolution_duration"]
    ) * 100

    s["health_score"] = score.round(2)
    s["health_level"] = s["health_score"].apply(health_level)
    return s

def build_alerts(issue_ops_long, openrank_long, end_month: str):
    
    iss = issue_ops_long[issue_ops_long["month"] == end_month].copy()
    or_end = openrank_long[openrank_long["month"] == end_month][["repo_full","openrank"]].rename(columns={"openrank":"openrank_end"})
    iss = iss.merge(or_end, on="repo_full", how="left")
    iss["backlog_end"] = iss["issues_new"] - iss["issues_closed"]

    alerts = []

    # 1) Issue 首响慢
    for _, r in iss.dropna(subset=["issue_response_time"]).iterrows():
        v = r["issue_response_time"]
        if v > 14:
            alerts.append((r["repo_full"], end_month, "Issue首响过慢", "红", "issue_response_time", v, 14, "首响时间>14天，建议建立 triage 机制"))
        elif v > 7:
            alerts.append((r["repo_full"], end_month, "Issue首响偏慢", "黄", "issue_response_time", v, 7, "首响时间>7天，建议增加值班/标签分流"))

    # 2) 积压风险
    for _, r in iss.dropna(subset=["backlog_end"]).iterrows():
        v = r["backlog_end"]
        if v > 50:
            alerts.append((r["repo_full"], end_month, "Issue积压严重", "红", "backlog_end", v, 50, "新增-关闭>50，积压上升"))
        elif v > 10:
            alerts.append((r["repo_full"], end_month, "Issue积压上升", "黄", "backlog_end", v, 10, "新增>关闭，积压开始累积"))

    df = pd.DataFrame(alerts, columns=["repo_full","month","alert_type","severity","metric","value","threshold","reason"])
    return df

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True, help="Step1 生成 CSV 的 out 目录")
    ap.add_argument("--start_month", required=True, help="例如 2020-01")
    ap.add_argument("--end_month", required=True, help="例如 2023-03")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)

    openrank_long = pd.read_csv(out_dir / "openrank_long.csv")
    issue_ops_long = pd.read_csv(out_dir / "issue_ops_long.csv")
    pr_ops_long = pd.read_csv(out_dir / "pr_ops_long.csv")

    snap = build_end_snapshot(openrank_long, issue_ops_long, pr_ops_long, args.end_month, args.start_month)
    health_end = compute_health_score(snap)

    alerts_end = build_alerts(issue_ops_long, openrank_long, args.end_month)

    health_end.to_csv(out_dir / "health_score_end.csv", index=False, encoding="utf-8-sig")
    alerts_end.to_csv(out_dir / "alerts_end.csv", index=False, encoding="utf-8-sig")

    print("Done:")
    print(" -", out_dir / "health_score_end.csv")
    print(" -", out_dir / "alerts_end.csv")
