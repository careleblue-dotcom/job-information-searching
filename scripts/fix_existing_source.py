#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性数据修复脚本：把 all_jobs.json 中 source 为空/None 的条目补为默认值。
新增数据已在 shared._ensure_source 兜底，此脚本只用于修复历史存量。
运行：python scripts/fix_existing_source.py
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_SOURCE

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'all_jobs.json')


def main():
    with open(DATA_FILE, encoding='utf-8') as f:
        data = json.load(f)

    fixed = 0
    for item in data:
        if not item.get('source'):
            item['source'] = DEFAULT_SOURCE
            fixed += 1

    # 备份后写回
    backup = DATA_FILE.replace('.json', f'_backup_source_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(backup, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'修复完成：共 {len(data)} 条，其中 {fixed} 条 source 已补为 "{DEFAULT_SOURCE}"')
    print(f'备份已保存到：{backup}')


if __name__ == '__main__':
    main()
