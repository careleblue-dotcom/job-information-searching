#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国务院国资委招聘信息爬虫 - 抓取央企国企招聘公告
同时抓取中国公共招聘网中央企业招聘信息
"""

from bs4 import BeautifulSoup
import time
import re
from config import HEADERS, DELAY
from shared import fetch_page, parse_date, save_and_merge, crawl_job_detail, logger

# 国务院国资委招聘专栏
SASAC_URL = "http://wap.sasac.gov.cn/n2588035/n2588325/n2588350/index.html"

# 中国公共招聘网 - 中央企业招聘应届高校毕业生信息公开
PUBLIC_JOB_URL = "http://www.job.mohrss.gov.cn/qyzp/index.jhtml"


def crawl_sasac():
    """爬取国务院国资委招聘信息"""
    logger.info('开始爬取国务院国资委招聘: %s', SASAC_URL)

    jobs = []
    html = fetch_page(SASAC_URL)
    if not html:
        logger.error('无法获取国资委招聘页面')
        return jobs

    soup = BeautifulSoup(html, 'html.parser')

    # 查找所有链接
    links = soup.find_all('a', href=True)
    job_links = []

    for link in links:
        href = link['href']
        text = link.get_text(strip=True)
        if not text or len(text) < 5:
            continue

        # 过滤招聘相关链接
        if any(kw in text for kw in ['招聘', '招聘公告', '校园招聘', '社会招聘', '公开招聘', '选调']):
            if href.startswith('http'):
                full_url = href
            elif href.startswith('/'):
                full_url = f"http://wap.sasac.gov.cn{href}"
            else:
                full_url = f"http://wap.sasac.gov.cn/n2588035/n2588325/n2588350/{href}"

            job_links.append({'url': full_url, 'title': text})

    # 提取日期
    for item in job_links:
        # 尝试从链接周围文本提取日期
        for elem in soup.find_all('a', href=True):
            if elem['href'] in item['url'] or elem['href'] == item['url']:
                parent = elem.parent
                if parent:
                    date_match = re.search(r'(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)', parent.get_text())
                    if date_match:
                        item['date'] = date_match.group(1)
                break
        if 'date' not in item:
            # 从标题末尾提取日期 [05-14]
            date_match = re.search(r'\[(\d{2}-\d{2})\]', item['title'])
            if date_match:
                item['date'] = f"2026-{date_match.group(1)}"

    logger.info('找到 %d 个招聘链接', len(job_links))

    for i, item in enumerate(job_links[:20], 1):
        logger.info('[%d/%d] 处理: %s', i, min(20, len(job_links)), item['title'][:50])

        job_data = crawl_job_detail(item['url'], '国务院国资委')
        if job_data:
            job_data['category'] = '央企招聘'
            if item.get('date') and not job_data.get('publish_date'):
                job_data['publish_date'] = parse_date(item['date'])
            jobs.append(job_data)
        else:
            # 保存基础信息
            jobs.append({
                'title': item['title'],
                'url': item['url'],
                'publish_date': parse_date(item.get('date', '')),
                'category': '央企招聘',
                'source': '国务院国资委',
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'region': '全国',
            })

        time.sleep(DELAY)

    logger.info('国资委爬取完成，共 %d 条', len(jobs))
    return jobs


def crawl_public_job():
    """爬取中国公共招聘网中央企业招聘信息"""
    logger.info('开始爬取中国公共招聘网央企招聘: %s', PUBLIC_JOB_URL)

    jobs = []
    html = fetch_page(PUBLIC_JOB_URL)
    if not html:
        logger.error('无法获取公共招聘网页面')
        return jobs

    soup = BeautifulSoup(html, 'html.parser')

    # 查找所有链接
    links = soup.find_all('a', href=True)
    job_links = []

    for link in links:
        href = link['href']
        text = link.get_text(strip=True)
        if not text or len(text) < 5:
            continue

        # 排除导航等非招聘链接
        if any(kw in text for kw in ['首页', '上一页', '下一页', '尾页', '加入收藏', '网站声明']):
            continue

        # 处理URL
        if href.startswith('http'):
            full_url = href
        elif href.startswith('/'):
            full_url = f"http://www.job.mohrss.gov.cn{href}"
        elif href.startswith('./'):
            full_url = f"http://www.job.mohrss.gov.cn/qyzp/{href[2:]}"
        else:
            full_url = f"http://www.job.mohrss.gov.cn/qyzp/{href}"

        # 提取日期（通常在链接旁边的文本中）
        date_text = ""
        parent = link.parent
        if parent:
            date_match = re.search(r'(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)', parent.get_text())
            if date_match:
                date_text = date_match.group(1)

        job_links.append({'url': full_url, 'title': text, 'date': date_text})

    logger.info('找到 %d 个招聘链接', len(job_links))

    for i, item in enumerate(job_links[:15], 1):
        logger.info('[%d/%d] 处理: %s', i, min(15, len(job_links)), item['title'][:50])

        job_data = crawl_job_detail(item['url'], '中国公共招聘网')
        if job_data:
            job_data['category'] = '央企招聘'
            if item.get('date') and not job_data.get('publish_date'):
                job_data['publish_date'] = parse_date(item['date'])
            jobs.append(job_data)
        else:
            jobs.append({
                'title': item['title'],
                'url': item['url'],
                'publish_date': parse_date(item.get('date', '')),
                'category': '央企招聘',
                'source': '中国公共招聘网',
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'region': '全国',
            })

        time.sleep(DELAY)

    logger.info('公共招聘网爬取完成，共 %d 条', len(jobs))
    return jobs


def main():
    print("=" * 60)
    print("央企国企招聘信息爬虫")
    print("=" * 60)

    all_jobs = []

    # 爬取国资委
    sasac_jobs = crawl_sasac()
    all_jobs.extend(sasac_jobs)

    time.sleep(DELAY * 2)

    # 爬取公共招聘网
    pub_jobs = crawl_public_job()
    all_jobs.extend(pub_jobs)

    if all_jobs:
        save_and_merge(all_jobs)
        print(f"\n爬取完成！")
        print(f"  国资委招聘: {len(sasac_jobs)} 条")
        print(f"  公共招聘网: {len(pub_jobs)} 条")
        print(f"  合计: {len(all_jobs)} 条")
    else:
        print("\n[警告] 未获取到数据")


if __name__ == '__main__':
    main()
