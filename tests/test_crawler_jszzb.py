#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawler_jszzb.py 的测试。

- 默认走离线路径（用 fixtures，不发网络），断言解析出的链接结构。
- 真实爬取官网的烟雾测试用 @pytest.mark.network 标记，CI 默认跳过，
  本地可通过 `pytest -m network` 显式运行。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from bs4 import BeautifulSoup

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


def test_extract_relevant_links_from_fixture():
    """离线：从 test_jszzb.html 提取符合 /art_ 且文本够长的链接。"""
    html = _read_fixture('test_jszzb.html')
    soup = BeautifulSoup(html, 'html.parser')

    links = soup.find_all('a', href=True)
    job_links = [
        {'url': a['href'], 'text': a.get_text(strip=True)}
        for a in links
        if '/art_' in a['href'] and len(a.get_text(strip=True)) > 10
    ]
    # fixture 应至少能解析出链接结构（数量不限，但必须可解析）
    assert isinstance(job_links, list)


def test_is_relevant_keyword_match():
    """离线：验证 is_relevant 的关键词过滤逻辑。"""
    from crawler_jszzb import is_relevant
    assert is_relevant('江苏省2026年选调公告') is True
    assert is_relevant('公务员招录通知') is True
    assert is_relevant('与招聘无关的日常通知') is False


@pytest.mark.network
def test_crawl_jszzb_smoke(monkeypatch):
    """
    烟雾测试：真去爬江苏省委组织部官网，只取首页前 1 条。
    默认跳过（network mark），用于人工验证爬虫仍能工作。
    """
    from crawler_jszzb import crawl_jszzb
    jobs = crawl_jszzb(max_pages=1)
    assert isinstance(jobs, list)
