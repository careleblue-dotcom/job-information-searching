#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一列表页发现爬虫（数据持续增长的核心引擎）。

问题背景：data/urls.json 是手动收集的一次性详情页快照，爬过一次就被
seen_urls.json 永久标记，之后定时任务每天"空转"、数据量无法增长。

本模块改为"列表页驱动"：每个数据源配置一个公告列表页（可翻页），每次运行：
  抓列表页 → 提取公告链接 → 增量过滤（跳过已爬 URL）→ 爬详情 → 合并入库。
列表页是持续滚动的，新发布的公告会被自动发现并入库，数据量随日期自然增长。

数据源配置见 config.LIST_SOURCES；运行入口：
  python crawler_discover.py          # 增量模式（推荐，定时任务用）
  python crawler_discover.py --full   # 忽略增量，全量重爬
  python crawler_discover.py --source 源名   # 只跑指定源（调试用）

每次运行结束会写 logs/crawl_report.json，CI 据此判断健康度与是否告警。
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LIST_SOURCES, CRAWL_REPORT_FILE, BASE_DELAY, DEFAULT_SOURCE
from shared import (
    fetch_page, crawl_job_detail, save_and_merge, jitter_delay,
    _load_seen, _save_seen, logger,
)

# 导航/装饰链接的常见文案，标题命中即丢弃
NOISE_KEYWORDS = ('首页', '上一页', '下一页', '尾页', '登录', '注册', '网站声明',
                  '收藏本站', '设为首页', '联系我们', '无障碍', 'English',
                  '返回列表', '更多', '打印本页', '分享')


def _page_url(cfg: dict, page: int) -> str:
    """构造第 page 页的列表页 URL；第 1 页直接用 list_url。"""
    pagination = cfg.get('pagination')
    if pagination and page > 1:
        pattern = pagination.get('pattern', 'index_{n}.html')
        return urljoin(cfg['list_url'], pattern.format(n=page))
    return cfg['list_url']


def extract_date_near_link(link) -> str:
    """从链接附近的文本中提取日期（YYYY-MM-DD / YYYY年M月D日），找不到返回空串。"""
    try:
        parent = link.parent
        if parent is None:
            return ""
        text = parent.get_text(strip=True)
        m = re.search(r'(\d{4})[-年.](\d{1,2})[-月.](\d{1,2})', text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    except Exception:
        pass
    return ""


def is_valid_link(cfg: dict, url: str, title: str) -> bool:
    """按配置过滤链接：URL 特征 + 标题长度 + 关键词白名单。"""
    title = (title or '').strip()
    if len(title) < cfg.get('title_min_len', 5):
        return False
    if any(k in title for k in NOISE_KEYWORDS):
        return False

    url_regex = cfg.get('url_regex')
    if url_regex and not re.search(url_regex, url):
        return False
    for sub in cfg.get('url_contains', []):
        if sub not in url:
            return False
    for sub in cfg.get('url_excludes', []):
        if sub in url:
            return False

    keywords = cfg.get('keywords')
    if keywords and not any(k in title for k in keywords):
        return False
    return True


def discover_links(cfg: dict) -> list:
    """
    抓取列表页（含翻页）并提取候选公告链接。
    返回 [{'url': 绝对URL, 'title': 标题, 'date': 列表页日期或''}]。
    翻页时若新页链接与已收集的完全重复，视为到底，提前停止。
    """
    pagination = cfg.get('pagination')
    max_pages = pagination.get('max_pages', 1) if pagination else 1
    max_links = cfg.get('max_links', 25)

    collected = []          # 全部候选
    collected_urls = set()  # 已收集 URL（去重 + 同页检测）
    last_page_urls = set()  # 上一页的 URL 集合（同页检测）

    for page in range(1, max_pages + 1):
        page_url = _page_url(cfg, page)
        html = fetch_page(page_url)
        if not html:
            logger.warning('[%s] 第 %d 页获取失败: %s', cfg['name'], page, page_url)
            break

        soup = BeautifulSoup(html, 'html.parser')
        page_urls = set()
        added = 0
        for a in soup.find_all('a', href=True):
            href = (a.get('href') or '').strip()
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            full_url = urljoin(page_url, href)
            if not is_valid_link(cfg, full_url, title):
                continue
            if full_url in collected_urls:
                page_urls.add(full_url)
                continue
            collected_urls.add(full_url)
            page_urls.add(full_url)
            collected.append({
                'url': full_url,
                'title': title,
                'date': extract_date_near_link(a),
            })
            added += 1
            if len(collected) >= max_links:
                break

        logger.info('[%s] 第 %d 页: 新增 %d 个链接, 累计 %d 个',
                    cfg['name'], page, added, len(collected))

        # 同页/到底检测：本页所有链接都已在上一页见过 → 停止翻页
        if page > 1 and page_urls and page_urls.issubset(last_page_urls):
            logger.info('[%s] 第 %d 页与上一页重复，停止翻页', cfg['name'], page)
            break
        last_page_urls = page_urls

        if len(collected) >= max_links:
            break
        if page < max_pages:
            time.sleep(BASE_DELAY)

    return collected[:max_links]


def crawl_list_source(cfg: dict, use_seen: bool = True) -> dict:
    """
    爬取单个列表源：发现链接 → 增量过滤 → 爬详情 → 合并入库。
    返回统计 dict（供整体报告聚合）。
    """
    source_name = cfg.get('source') or cfg['name']
    category = cfg.get('category', '')
    stats = {
        'name': cfg['name'],
        'status': 'ok',
        'discovered': 0,
        'new': 0,
        'skipped': 0,
        'failed': 0,
        'error': '',
    }

    try:
        links = discover_links(cfg)
        stats['discovered'] = len(links)
        if not links:
            logger.warning('[%s] 未发现任何公告链接，检查站点是否改版', cfg['name'])
            stats['status'] = 'warn'
            return stats

        seen = _load_seen() if use_seen else set()

        batch = []
        for item in links:
            url = item['url']
            if use_seen and url in seen:
                stats['skipped'] += 1
                continue

            job_data = crawl_job_detail(
                url, source_name,
                partial_meta={
                    'title': item['title'],
                    'category': category,
                    'publish_date': item.get('date'),
                },
            )
            if job_data is None:
                stats['failed'] += 1
                continue

            # 详情页没解析出日期时，用列表页日期兜底
            if item.get('date') and not job_data.get('publish_date'):
                job_data['publish_date'] = item['date']
            # 详情页没解析出分类时，用源配置的分类兜底
            if category and job_data.get('category') in ('其他', ''):
                job_data['category'] = category

            batch.append(job_data)
            seen.add(url)
            stats['new'] += 1

            if len(batch) >= 10:
                save_and_merge(batch)
                if use_seen:
                    _save_seen(seen)
                batch = []
            jitter_delay()

        if batch:
            save_and_merge(batch)
            if use_seen:
                _save_seen(seen)

        if stats['new'] == 0 and stats['discovered'] > 0:
            logger.info('[%s] 全部 %d 条已爬过（增量无新增）',
                        cfg['name'], stats['discovered'])
        logger.info('[%s] 完成: 发现 %d, 新增 %d, 跳过 %d, 失败 %d',
                    cfg['name'], stats['discovered'], stats['new'],
                    stats['skipped'], stats['failed'])

    except Exception as e:
        logger.error('[%s] 爬取异常: %s', cfg['name'], str(e))
        stats['status'] = 'error'
        stats['error'] = str(e)[:200]

    return stats


def main():
    parser = argparse.ArgumentParser(description='列表页发现爬虫（数据持续增长）')
    parser.add_argument('--full', action='store_true', help='忽略增量状态，全量重爬')
    parser.add_argument('--source', default='', help='只跑指定源（按 name 匹配）')
    args = parser.parse_args()

    print("=" * 60)
    print("列表页发现爬虫")
    print(f"模式: {'全量(--full)' if args.full else '增量(跳过已爬)'}")
    print(f"数据源数: {len(LIST_SOURCES)}")
    print("=" * 60)

    targets = LIST_SOURCES
    if args.source:
        targets = [c for c in LIST_SOURCES if args.source in c['name']]
        if not targets:
            print(f"[错误] 没有找到包含 '{args.source}' 的数据源")
            print("可用源:", ' | '.join(c['name'] for c in LIST_SOURCES))
            return

    all_stats = []
    for cfg in targets:
        logger.info('开始处理数据源: %s', cfg['name'])
        stats = crawl_list_source(cfg, use_seen=not args.full)
        all_stats.append(stats)
        time.sleep(BASE_DELAY * 2)

    total_new = sum(s['new'] for s in all_stats)
    total_discovered = sum(s['discovered'] for s in all_stats)
    total_failed = sum(s['failed'] for s in all_stats)

    # 健康度: 有源报错或发现数为 0 的源占比过高 → warn/error
    bad_sources = [s for s in all_stats if s['status'] != 'ok' or s['discovered'] == 0]
    if all_stats and len(bad_sources) == len(all_stats):
        health = 'error'
    elif bad_sources:
        health = 'warn'
    else:
        health = 'ok'

    report = {
        'run_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'mode': 'full' if args.full else 'incremental',
        'health': health,
        'total_discovered': total_discovered,
        'total_new': total_new,
        'total_failed': total_failed,
        'sources': all_stats,
        'bad_sources': [s['name'] for s in bad_sources],
    }
    try:
        os.makedirs(os.path.dirname(CRAWL_REPORT_FILE), exist_ok=True)
        with open(CRAWL_REPORT_FILE, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info('爬取报告已写入: %s', CRAWL_REPORT_FILE)
    except Exception as e:
        logger.warning('写报告失败(非阻塞): %s', e)

    # 保活: 更新 _meta.json 的 last_checked（即使 0 新增也有 git 变更，
    # 避免 GitHub Actions 对 60 天无活动的仓库自动禁用定时任务）
    _touch_meta_checked()

    print("\n" + "=" * 60)
    print("爬取完成！")
    print(f"  发现链接: {total_discovered} 个")
    print(f"  新增入库: {total_new} 条")
    print(f"  失败: {total_failed} 条")
    print(f"  健康度: {health}")
    if bad_sources:
        print("  异常源: " + ", ".join(s['name'] for s in bad_sources))
    print("=" * 60)


def _touch_meta_checked() -> None:
    """更新 data/_meta.json 的 last_checked 字段（不影响 last_updated）。"""
    meta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', '_meta.json')
    try:
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        meta['last_checked'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning('写 _meta.json 保活字段失败(非阻塞): %s', e)


if __name__ == '__main__':
    main()
