# OpenSODA · OpenRank Cup（W2）参赛作品  
## Top300 开源项目 Issue「净积压」预警可视化大屏（DataEase）

本仓库用于提交 OpenSODA 作品类 **W2（可视化大屏）** 赛道作品。作品基于 Top300 指标数据（`top_300_metrics`，OpenDigger 指标体系，含 OpenRank），通过 Python 脚本将“按仓库分目录、按指标分 JSON、按月份为 key/value”的数据结构摊平成 BI 友好的 CSV，并使用 **DataEase** 完成可视化大屏。

## 0. 项目分工

对对队的成员为耿紫琪和章欣怡，分别负责项目的以下部分：
- `耿紫琪`：alert_end.csv图表分析，DataEase可视化大屏制作，PPT制作，参赛视频录制
- `章欣怡`：数据处理脚本编写，数据报告撰写

**当前版本的核心问题：**  
> **如何快速识别 Top300 项目中“当月 Issue 净积压变化量（issues_new - issues_closed）显著上升”的项目，并形成可视化预警看板，辅助社区治理与资源调度？**

---

## 1. 仓库内容与文件清单

提交的内容包括：**3 个处理脚本 + 7 张 CSV 表 + 2 张初赛静态图 + 1 张 DataEase 大屏截图 + 1 份数据报告 + 1 份PPT + 1个解说视频**。

### 1) Python 脚本（3 个）
- `mini_report.py`  
  初步分析脚本：生成 OpenRank Top15、增长 Top15 的 CSV 与静态图，并输出初版说明文档（见 `report.md`）。
- `build_long_tables.py`  
  完整指标摊平脚本：将每个仓库目录下的多类指标 JSON 摊平成可做趋势/下钻的长表（openrank_long / issue_ops_long / pr_ops_long）。
- `build_health_and_alerts.py`  
  期末快照与预警脚本：基于长表生成期末月的综合健康度快照（health_score_end）与预警清单（alerts_end）。

### 2) CSV 表（7 张 CSV）
- `openrank_top_end.csv`：期末（2023-03）OpenRank Top15
- `openrank_top_growth.csv`：区间增长 Top15（2020-01→2023-03，含 start/end/delta）
- `openrank_long.csv`：OpenRank 月度时序（repo × month）
- `issue_ops_long.csv`：Issue 治理运营时序（repo × month × 指标）
- `pr_ops_long.csv`：PR（change_request）运营指标月度长表（repo × month × 指标）
- `health_score_end.csv`：期末健康度快照与综合评分尝试
- `alerts_end.csv`：期末治理预警清单（本次大屏核心数据源）

### 3) 初赛静态图（2 张）
- `openrank_top_end.png`：期末 Top15 静态图
- `openrank_top_growth.png`：增长 Top15 静态图

### 4) DataEase 大屏成果图（1 张）
- `dataease_dashboard.png`：DataEase 大屏截图

### 5) 项目解说（3部分）
- `数据报告.pdf` ：详细的数据处理过程与分析结论
- `基于 OpenDigger Top300 指标的开源项目 Issue 净积压预警可视化大屏.pptx` ：数据大屏介绍
- `视频` ：项目解说
---

## 2. 数据来源

- 数据来源：OpenDigger Top300 指标数据集  
- 下载链接：https://oss.x-lab.info/openSODA_dataset/top_300_metrics.zip
- 覆盖时间：**2020-01 ～ 2023-03**
- 数据对象：Top300 GitHub 开源项目
- 数据形态：**按项目目录拆分的多指标 JSON 文件**
---

## 3. 复现步骤

### 0) 环境准备
- Python 3.9+（建议 3.10/3.11）
- 依赖：
  - pandas
  - numpy
  - matplotlib（仅用于画图/导出 png）

安装：
```bash
python -m pip install -U pandas numpy matplotlib
```
-下载数据，并将top300_metrics和脚本放在同一个目录下
### 1) Step 1：生成 long tables
```bash
python build_long_tables.py \
  --metrics_dir top_300_metrics \
  --out_dir out
```

你将得到：
- `out/openrank_long.csv`
- `out/issue_ops_long.csv`
- `out/pr_ops_long.csv`

### 2) Step 2：生成期末健康度与告警
```bash
python build_health_and_alerts.py \
  --out_dir out \
  --start_month 2020-01 \
  --end_month 2023-03
```

你将得到：
- `out/health_score_end.csv`
- `out/alerts_end.csv`

### 3) Step 3：生成轻量化项目影响力图表
和前两步类似，运行mini_report.py脚本，
它会从 `top_300_metrics/**/openrank.json` 读取数据，输出out文件夹，包含以下内容：
- `out/openrank_top_end.csv`：期末影响力 Top15（OpenRank(2023-03)）
- `out/openrank_top_growth.csv`：区间增长 Top15（OpenRank(2023-03)-OpenRank(2020-01)）

- `out/openrank_top_end.png` / `out/openrank_top_growth.png`：对应图表





