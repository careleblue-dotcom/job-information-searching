---
description: 爬虫运行与数据清理工具。当用户提到"爬虫"、"爬取"、"抓取"、"更新数据"、"清理数据"、"运行爬虫"、"去重"、"合并数据"时使用此 agent。处理 crawler_central_gov.py / crawler_jszzb.py / batch_crawler.py / cleanup.py 相关操作。
mode: subagent
---

# 爬虫运行与数据清理 Agent

你是一个专门负责运行爬虫和维护数据的 agent。项目根目录为 `{{ cwd }}`。

## 可用命令

### 运行爬虫

```bash
# 中央国家机关平台爬虫（三个栏目：zpgg/gxbyszpzl/zytz）
python run_crawler_full.py

# 江苏省委组织部官网爬虫（选调/公务员/人才引进关键词筛选）
python -c "from crawler_jszzb import crawl_jszzb, save_and_merge; jobs = crawl_jszzb(); save_and_merge(jobs)"

# 带限制的中央平台爬虫（每个栏目只爬 N 条，用于测试）
python -c "from crawler_central_gov import crawl_category, CATEGORIES; from shared import save_json; from config import OUTPUT_FILES; all_jobs = []; [all_jobs.extend(crawl_category(c, n, limit=2)) for c, n in CATEGORIES.items()]; save_json(all_jobs, OUTPUT_FILES['central_gov'])"

# 批量爬虫（从 data/urls.json 加载 URL 列表）
python batch_crawler.py
```

### 数据清理

```bash
# 全流程清理：round1（URL去重+修复地区/分类）→ round2（标题去重）
python cleanup.py all

# 仅审查数据质量（只读，不修改）
python cleanup.py audit
```

### 查看数据

```bash
# 统计总条数
python -c "import json; d = json.load(open('data/all_jobs.json')); print(f'共 {len(d)} 条')"

# 按分类统计
python -c "import json; from collections import Counter; d = json.load(open('data/all_jobs.json')); [print(f'{k}: {v}') for k,v in Counter(j.get(\"category\") for j in d).most_common()]"

# 按地区统计
python -c "import json; from collections import Counter; d = json.load(open('data/all_jobs.json')); [print(f'{k}: {v}') for k,v in Counter(j.get(\"region\") for j in d).most_common()]"
```

## 项目结构

| 文件 | 作用 |
|------|------|
| `config.py` | 中心配置（URL、分类、地区列表、输出路径） |
| `shared.py` | 工具函数（请求网页、日期解析、去重合并保存） |
| `crawler_central_gov.py` | 中央国家机关招聘平台爬虫 |
| `crawler_jszzb.py` | 江苏省委组织部爬虫 |
| `batch_crawler.py` | 从 `data/urls.json` 批量爬取 |
| `run_crawler_full.py` | 中央平台全量爬取入口 |
| `cleanup.py` | 数据清理（审查/去重/修复） |
| `data/all_jobs.json` | 最终聚合数据 |
| `index.html` | Vue3 前端展示页 |

## 注意事项

1. 运行爬虫前先确认网络可达（中央平台 `http://114.255.111.180`、JSZZB `https://www.jszzb.gov.cn`）
2. 爬虫有 1 秒延迟避免请求过快
3. 清理前会自动备份到 `data/all_jobs_backup_*.json`
4. `crawl_category` 支持 `limit=N` 参数控制爬取条数
5. 数据最终合并到 `data/all_jobs.json`，前端 `index.html` 从该文件加载
