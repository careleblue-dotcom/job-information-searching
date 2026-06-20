#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from shared import batch_crawl, save_and_merge, logger
from config import OUTPUT_FILES


def load_urls(filename=None):
    if filename is None:
        filename = os.path.join(os.path.dirname(__file__), 'data', 'urls.json')
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = [(item['url'], item['source']) for item in data]
        logger.info('从 %s 加载了 %d 个URL', filename, len(items))
        return items
    except FileNotFoundError:
        logger.error('文件不存在: %s', filename)
        return []
    except Exception as e:
        logger.error('加载URL文件失败: %s', str(e))
        return []


if __name__ == '__main__':
    print("=" * 60)
    print("批量爬取选调生/公务员考试公告")
    print("=" * 60)

    urls_with_source = load_urls()

    if not urls_with_source:
        print("\n[错误] 没有加载到任何URL，请检查 data/urls.json 文件")
    else:
        jobs = batch_crawl(urls_with_source, save_interval=10, output_file=OUTPUT_FILES["all_jobs"])

        if jobs:
            print(f"\n[完成] 本次共爬取 {len(jobs)} 条数据")
        else:
            print("\n[警告] 未获取到数据")
