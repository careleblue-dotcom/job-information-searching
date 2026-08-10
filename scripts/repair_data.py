#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性数据修复：修复历史存量记录的数据质量问题。

问题背景：早期爬虫对北京人社局/中央机关/山西等政府站的 URL 文件名日期
（tYYYYMMDD 格式）提取失败，导致 publish_date 误抓页面里其他日期
（截止时间/建站年份等）；且部分页面正文 fallback 到 body 抓到导航噪声。

修复策略（按优先级）：
1. URL 含 tYYYYMMDD 且与 publish_date 不符 → 以 URL 日期为准（政府站文件名规范，权威来源）
2. publish_date 为明显错误年份（<2020）且 URL 无日期 → 置空（诚实显示，前端空日期沉底）
3. 正文前 600 字含导航噪声 → 用修复后的解析器重新抓取；重抓后仍噪声/失败 → 删除
4. 备份后写回

运行：python scripts/repair_data.py
"""
import os
import re
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import crawl_job_detail, logger

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'data', 'all_jobs.json')

# 政府站导航/无障碍提示等噪声词（命中即视为正文污染）
NAV_WORDS = ('无障碍', '专属空间', '高级搜索', '政务服务网', '智能问答', '网站地图', '我要留言')


def url_date(u: str) -> str:
    """从 URL 文件名提取 tYYYYMMDD 发布日期；无则返回空串。"""
    m = re.search(r'/t(\d{8})', u or '')
    return f'{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}' if m else ''


def is_noisy(content: str) -> bool:
    """正文前 600 字是否含导航噪声。"""
    head = (content or '')[:600]
    return any(w in head for w in NAV_WORDS)


def main():
    with open(DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)

    stats = {'fixed_date': 0, 'emptied': 0, 'refetched': 0, 'deleted': 0}
    kept = []

    for j in data:
        url = j.get('url', '')
        ud = url_date(url)
        pd = (j.get('publish_date') or '').strip()

        # 1. URL 日期权威修正
        if ud and pd != ud:
            j['publish_date'] = ud
            stats['fixed_date'] += 1
        # 2. 明显错误年份且无法从 URL 修正 → 置空
        elif pd and pd[:4].isdigit() and int(pd[:4]) < 2020 and not ud:
            j['publish_date'] = ''
            stats['emptied'] += 1

        # 3. 噪声正文 → 重抓
        if is_noisy(j.get('content', '')):
            new = crawl_job_detail(
                url, j.get('source', ''),
                partial_meta={
                    'title': j.get('title', ''),
                    'category': j.get('category', ''),
                    'publish_date': ud or pd,
                },
            )
            good = (new is not None
                    and not is_noisy(new.get('content', ''))
                    and len((new.get('content') or '')) >= 20)
            if good:
                new['publish_date'] = ud or new.get('publish_date') or pd
                new['title'] = new.get('title') or j.get('title', '')
                kept.append(new)
                stats['refetched'] += 1
                logger.info('重抓修复: %s', url)
                continue
            stats['deleted'] += 1
            logger.warning('重抓失败/仍噪声, 删除: %s', url)
            continue

        kept.append(j)

    # 备份后写回
    backup = DATA_FILE.replace('.json', f'_backup_repair_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(backup, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    print(f"修复完成: 原 {len(data)} 条 → 现 {len(kept)} 条")
    print(f"  日期修正: {stats['fixed_date']} 条 | 错误年份置空: {stats['emptied']} 条")
    print(f"  噪声重抓成功: {stats['refetched']} 条 | 删除: {stats['deleted']} 条")
    print(f"  备份: {backup}")


if __name__ == '__main__':
    main()

