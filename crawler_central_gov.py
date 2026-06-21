#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
from config import HEADERS, DELAY, OUTPUT_FILES, CENTRAL_GOV
from shared import fetch_page, parse_date, save_json, crawl_job_detail, logger

BASE_URL = CENTRAL_GOV["BASE_URL"]
CATEGORIES = CENTRAL_GOV["CATEGORIES"]
OUTPUT_FILE = OUTPUT_FILES["central_gov"]

# 从 BASE_URL 派生 host（避免在拼接 URL 时硬编码 IP）
_SCHEME, _NETLOC = re.match(r'(https?://)([^/]+)', BASE_URL).group(1), re.match(r'https?://([^/]+)', BASE_URL).group(1)
HOST_ORIGIN = f"{_SCHEME}{_NETLOC}"  # 如 http://114.255.111.180


def crawl_category(category_code, category_name, limit=20):
    logger.info('开始爬取栏目: %s (%s)', category_name, category_code)

    category_url = f"{BASE_URL}/{category_code}"

    html = fetch_page(category_url)
    if not html:
        logger.error('无法获取栏目页面: %s', category_url)
        return []

    soup = BeautifulSoup(html, 'html.parser')

    selectors = [
        'ul li a',
        'div.list-item a',
        'tr td a',
        'a[href$=".html"]',
    ]

    links = []
    for selector in selectors:
        links = soup.select(selector)
        if links:
            break

    if not links:
        logger.warning('未找到招聘信息链接')
        return []

    logger.info('找到 %d 个链接', len(links))

    job_list = []

    for idx, link in enumerate(links[:limit], 1):
        href = link.get('href', '')
        title = link.get_text(strip=True)

        if not href or not title or len(title) < 5:
            continue

        if href.startswith('http'):
            full_url = href
        elif href.startswith('./'):
            full_url = f"{category_url}/{href[2:]}"
        elif href.startswith('/'):
            full_url = f"{HOST_ORIGIN}{href}"
        else:
            full_url = f"{category_url}/{href}"

        date_str = ""
        parent = link.parent
        if parent:
            date_elem = parent.find(class_=lambda x: x and ('date' in x.lower() or 'time' in x.lower()))
            if date_elem:
                date_str = date_elem.get_text(strip=True)

        logger.info('[%d] 处理: %s', idx, title[:50])

        job_detail = crawl_job_detail(full_url, category_name)

        if job_detail:
            job_detail['title'] = title
            job_detail['url'] = full_url
            job_detail['category'] = category_name
            job_detail['category_code'] = category_code
            if date_str:
                job_detail['publish_date'] = parse_date(date_str)

            job_list.append(job_detail)
        else:
            job_list.append({
                'title': title,
                'url': full_url,
                'category': category_name,
                'category_code': category_code,
                'publish_date': parse_date(date_str),
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error': '详情页获取失败'
            })
            logger.warning('详情页获取失败，仅保存基本信息: %s', title[:50])

        time.sleep(DELAY)

    logger.info('栏目 %s 爬取完成，共 %d 条', category_name, len(job_list))
    return job_list


def main():
    logger.info('中央和国家机关事业单位公开招聘平台 - 爬虫启动')
    logger.info('开始时间: %s', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    all_jobs = []

    for category_code, category_name in CATEGORIES.items():
        jobs = crawl_category(category_code, category_name)
        all_jobs.extend(jobs)
        time.sleep(DELAY * 2)

    if all_jobs:
        save_json(all_jobs, OUTPUT_FILE)
        logger.info('爬取完成！总条数: %d', len(all_jobs))
        for category_code, category_name in CATEGORIES.items():
            count = len([j for j in all_jobs if j.get('category_code') == category_code])
            logger.info('  %s: %d 条', category_name, count)
    else:
        logger.warning('未爬取到任何数据')

    logger.info('结束时间: %s', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


if __name__ == "__main__":
    main()
