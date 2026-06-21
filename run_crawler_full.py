#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
sys.path.insert(0, '.')

from crawler_central_gov import crawl_category, CATEGORIES
from shared import save_json, logger
from config import OUTPUT_FILES

OUTPUT_FILE = OUTPUT_FILES["central_gov"]


def main():
    print("="*60)
    print("运行完整爬虫（无限制）")
    print("="*60)

    all_jobs = []

    for category_code, category_name in CATEGORIES.items():
        logger.info('处理栏目: %s (%s)', category_name, category_code)
        jobs = crawl_category(category_code, category_name)
        all_jobs.extend(jobs)
        time.sleep(2)

    if all_jobs:
        save_json(all_jobs, OUTPUT_FILE)
        print(f"\n[成功] 爬取完成！")
        print(f"  总条数: {len(all_jobs)}")
        print(f"  数据已保存到: {OUTPUT_FILE}")
        print(f"\n统计信息：")
        for category_code, category_name in CATEGORIES.items():
            count = len([j for j in all_jobs if j.get('category_code') == category_code])
            print(f"  {category_name}: {count} 条")
    else:
        print("\n[警告] 未爬取到任何数据")


if __name__ == "__main__":
    main()
