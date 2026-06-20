#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
广东省委组织部官网爬虫 - 抓取选调生/公务员/事业单位招聘公告
"""

from bs4 import BeautifulSoup
import time
import re
from config import HEADERS, DELAY
from shared import fetch_page, parse_date, save_and_merge, crawl_job_detail, logger

BASE_URL = "https://www.gdzz.gov.cn"
LIST_URL = "https://www.gdzz.gov.cn/tzgg/"
KEYWORDS = ['选调', '公务员', '人才引进', '事业单位', '编制', '招聘', '录用', '遴选', '招考']


def is_relevant(title, content=""):
    text = title + content
    return any(keyword in text for keyword in KEYWORDS)


def crawl_gdzzb(max_pages=5):
    logger.info('开始爬取广东省委组织部官网: %s', LIST_URL)

    jobs = []

    try:
        for page in range(1, max_pages + 1):
            if page == 1:
                url = LIST_URL
            else:
                # 广东组织工作网分页模式
                url = f"{LIST_URL}index_{page}.html"

            logger.info('正在爬取第 %d 页: %s', page, url)
            html = fetch_page(url)
            if not html:
                logger.warning('第 %d 页获取失败', page)
                continue

            soup = BeautifulSoup(html, 'html.parser')

            # 寻找所有链接
            links = soup.find_all('a', href=True)
            page_links = []
            for link in links:
                href = link['href']
                text = link.get_text(strip=True)

                if len(text) < 8:
                    continue

                if is_relevant(text):
                    if href.startswith('http'):
                        full_url = href
                    elif href.startswith('/'):
                        full_url = f"{BASE_URL}{href}"
                    elif href.startswith('./'):
                        full_url = f"{LIST_URL}{href[2:]}"
                    else:
                        full_url = f"{LIST_URL}{href}"

                    # 提取日期
                    date_text = ""
                    parent = link.parent
                    if parent:
                        date_elem = parent.find(class_=lambda x: x and ('date' in x.lower() or 'time' in x.lower()))
                        if date_elem:
                            date_text = date_elem.get_text(strip=True)
                        if not date_text:
                            # 检查td或span中的日期
                            for sibling in parent.find_all(['span', 'td', 'em'], recursive=False):
                                sib_text = sibling.get_text(strip=True)
                                if re.search(r'\d{4}[-年]\d{1,2}[-月]\d{1,2}', sib_text):
                                    date_text = sib_text
                                    break

                    page_links.append({'url': full_url, 'title': text, 'date': date_text})

            logger.info('第 %d 页找到 %d 个相关链接', page, len(page_links))

            # 去重
            seen = set()
            unique = []
            for item in page_links:
                if item['url'] not in seen:
                    seen.add(item['url'])
                    unique.append(item)

            for i, item in enumerate(unique[:10], 1):  # 每页最多取10条
                logger.info('[%d/%d] 处理: %s', i, min(10, len(unique)), item['title'][:50])

                job_data = crawl_job_detail(item['url'], '广东省委组织部官网')
                if job_data:
                    job_data['category'] = '选调生/公务员'
                    if item['date'] and not job_data.get('publish_date'):
                        job_data['publish_date'] = parse_date(item['date'])
                    jobs.append(job_data)

                time.sleep(DELAY)

            time.sleep(DELAY * 2)

        logger.info('爬取完成，共 %d 条数据', len(jobs))
        return jobs

    except Exception as e:
        logger.error('爬取失败: %s', str(e))
        import traceback
        traceback.print_exc()
        return jobs


if __name__ == '__main__':
    print("=" * 60)
    print("广东省委组织部官网爬虫")
    print("=" * 60)

    jobs = crawl_gdzzb(max_pages=5)

    if jobs:
        save_and_merge(jobs)
        print("\n" + "=" * 60)
        print("爬取完成！共 %d 条数据" % len(jobs))
        print("=" * 60)
    else:
        print("\n[警告] 未获取到数据")
