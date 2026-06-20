#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试爬虫 - 只爬取少量数据
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crawler_jszzb import crawl_jszzb
from shared import save_json


if __name__ == '__main__':
    print("开始测试爬虫（只爬取前3条）...")

    jobs = crawl_jszzb(max_pages=1)

    if jobs:
        test_jobs = jobs[:3]
        save_json(test_jobs, 'data/jszzb_test.json')

        print("\n" + "=" * 60)
        print("测试完成！")
        print(f"共爬取 {len(test_jobs)} 条数据")
        print("数据已保存到: data/jszzb_test.json")
        print("=" * 60)

        import json
        with open('data/jszzb_test.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        print("\n数据样本：")
        for i, item in enumerate(data, 1):
            print(f"\n[{i}] 标题: {item['title'][:50]}")
            print(f"    日期: {item.get('publish_date', '未知')}")
            print(f"    地区: {item.get('region', '未知')}")
            print(f"    URL: {item['url'][:80]}...")
    else:
        print("测试失败：未获取到数据")
