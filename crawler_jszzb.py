#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import time
import re
from config import HEADERS, DELAY, JSZZB
from shared import fetch_page, parse_date, save_and_merge, crawl_job_detail, logger

BASE_URL = JSZZB["BASE_URL"]
LIST_URL = JSZZB["LIST_URL"]
KEYWORDS = JSZZB["KEYWORDS"]


def is_relevant(title, content=""):
    text = title + content
    return any(keyword in text for keyword in KEYWORDS)


def crawl_jszzb(max_pages=3):
    logger.info('开始爬取江苏省委组织部官网: %s', LIST_URL)

    jobs = []

    try:
        html = fetch_page(LIST_URL)
        if not html:
            logger.error('无法获取列表页面')
            return jobs

        soup = BeautifulSoup(html, 'html.parser')

        links = soup.find_all('a', href=True)

        job_links = []
        for link in links:
            href = link['href']
            text = link.get_text(strip=True)

            if '/art_' in href and len(text) > 10:
                if is_relevant(text):
                    if href.startswith('http'):
                        full_url = href
                    elif href.startswith('./'):
                        full_url = f"{LIST_URL}/{href[2:]}"
                    elif href.startswith('/'):
                        full_url = f"{BASE_URL}{href}"
                    else:
                        full_url = f"{LIST_URL}/{href}"

                    job_links.append({'url': full_url, 'title': text})

        logger.info('找到 %d 个相关链接', len(job_links))

        seen_urls = set()
        unique_links = []
        for item in job_links:
            if item['url'] not in seen_urls:
                seen_urls.add(item['url'])
                unique_links.append(item)

        logger.info('去重后剩余 %d 个链接', len(unique_links))

        limit = min(20, max_pages * 10)
        for i, item in enumerate(unique_links[:limit], 1):
            logger.info('[%d/%d] 处理: %s', i, min(limit, len(unique_links)), item['title'][:50])

            job_data = crawl_job_detail(item['url'], '江苏省委组织部官网')
            if job_data:
                job_data['category'] = '选调生/公务员'
                jobs.append(job_data)

            time.sleep(DELAY)

        logger.info('爬取完成，共 %d 条数据', len(jobs))
        return jobs

    except Exception as e:
        logger.error('爬取失败: %s', str(e))
        import traceback
        traceback.print_exc()
        return jobs


if __name__ == '__main__':
    print("=" * 60)
    print("江苏省委组织部官网爬虫")
    print("=" * 60)

    jobs = crawl_jszzb(max_pages=3)

    if jobs:
        save_and_merge(jobs)
        print("\n" + "=" * 60)
        print("爬取完成！")
        print("=" * 60)
    else:
        print("\n[警告] 未获取到数据")
