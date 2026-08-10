#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawler_discover.py 的离线单元测试：不发任何网络请求。
覆盖：链接过滤规则、列表页链接提取、翻页构造与同页停止、
增量过滤逻辑、LIST_SOURCES 配置合法性。
运行：pytest tests/test_crawler_discover.py
"""
import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from bs4 import BeautifulSoup

from crawler_discover import (
    is_valid_link,
    discover_links,
    _page_url,
    extract_date_near_link,
    crawl_list_source,
)
from config import LIST_SOURCES

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')

# 通用测试配置
CFG = {
    'name': '测试源',
    'source': '测试来源',
    'category': '事业单位',
    'list_url': 'https://example.com/list/',
    'url_regex': r'/20\d{4}/t20\d{6,8}_?\d*\.html',
    'title_min_len': 8,
    'max_links': 10,
    'pagination': None,
}


# ─── is_valid_link ────────────────────────────────

def test_valid_link_passes():
    assert is_valid_link(CFG, 'https://example.com/list/202606/t20260615_123456.html',
                         '某单位2026年公开招聘公告') is True


def test_invalid_url_regex_rejected():
    assert is_valid_link(CFG, 'https://example.com/other/page.html', '某单位招聘公告') is False


def test_title_too_short_rejected():
    assert is_valid_link(CFG, 'https://example.com/list/202606/t20260615_123456.html', '短标题') is False


def test_noise_keyword_rejected():
    assert is_valid_link(CFG, 'https://example.com/list/202606/t20260615_123456.html',
                         '首页-某单位招聘公告') is False


def test_url_contains_rule():
    cfg = dict(CFG)
    cfg.pop('url_regex')
    cfg['url_contains'] = ['/gwy_zhaokaogonggao/']
    assert is_valid_link(cfg, 'https://example.com/html/gwy_zhaokaogonggao/7341.html', '某省2026年公务员招考公告内容') is True
    assert is_valid_link(cfg, 'https://example.com/html/other/7341.html', '某省2026年公务员招考公告内容') is False


def test_url_excludes_rule():
    cfg = dict(CFG)
    cfg.pop('url_regex')
    cfg['url_excludes'] = ['2025']
    assert is_valid_link(cfg, 'https://example.com/202606/a.html', '某省2026年招聘公告内容') is True
    assert is_valid_link(cfg, 'https://example.com/202506/a.html', '某省2026年招聘公告内容') is False


def test_keywords_whitelist():
    cfg = dict(CFG)
    cfg['keywords'] = ['招聘', '选调']
    assert is_valid_link(cfg, 'https://example.com/list/202606/t20260615_123456.html', '某省2026年选调公告内容') is True
    assert is_valid_link(cfg, 'https://example.com/list/202606/t20260615_123456.html', '某省2026年日常通知内容') is False


# ─── _page_url ────────────────────────────────────

def test_page_url_first_page_uses_list_url():
    cfg = dict(CFG)
    cfg['pagination'] = {'pattern': 'index_{n}.html', 'max_pages': 3}
    assert _page_url(cfg, 1) == 'https://example.com/list/'
    assert _page_url(cfg, 2) == 'https://example.com/list/index_2.html'


def test_page_url_no_pagination():
    assert _page_url(CFG, 2) == 'https://example.com/list/'


# ─── extract_date_near_link ───────────────────────

def test_extract_date_from_parent_text():
    html = '<ul><li><span>2026-06-15</span><a href="/x.html">招聘公告标题内容</a></li></ul>'
    soup = BeautifulSoup(html, 'html.parser')
    link = soup.find('a')
    assert extract_date_near_link(link) == '2026-06-15'


def test_extract_date_chinese_format():
    html = '<ul><li><span>2026年6月15日</span><a href="/x.html">招聘公告标题内容</a></li></ul>'
    soup = BeautifulSoup(html, 'html.parser')
    link = soup.find('a')
    assert extract_date_near_link(link) == '2026-06-15'


def test_extract_date_none_when_absent():
    html = '<ul><li><a href="/x.html">招聘公告标题内容</a></li></ul>'
    soup = BeautifulSoup(html, 'html.parser')
    link = soup.find('a')
    assert extract_date_near_link(link) == ''


# ─── discover_links（monkeypatch fetch_page）──────

PAGE1_HTML = """
<html><body><ul class="list">
  <li><span>2026-06-15</span><a href="./202606/t20260615_100001.html">某单位2026年公开招聘公告一</a></li>
  <li><span>2026-06-10</span><a href="./202606/t20260610_100002.html">某单位2026年公开招聘公告二</a></li>
  <li><span>2026-06-01</span><a href="./202605/t20260601_100003.html">某单位2026年公开招聘公告三</a></li>
  <li><a href="/about.html">关于本站导航链接</a></li>
  <li><a href="./202606/t20260601_100004.html">短</a></li>
</ul></body></html>
"""

PAGE2_HTML = """
<html><body><ul class="list">
  <li><span>2026-05-20</span><a href="./202605/t20260520_100005.html">某单位2026年公开招聘公告四</a></li>
  <li><span>2026-05-10</span><a href="./202605/t20260510_100006.html">某单位2026年公开招聘公告五</a></li>
</ul></body></html>
"""


def _make_fetch(pages: dict):
    """构造 fetch_page 替身：按 URL 返回对应 HTML，未命中返回 None。"""
    def fake_fetch(url, timeout=30, retries=3):
        return pages.get(url)
    return fake_fetch


def test_discover_links_extracts_and_filters(monkeypatch):
    cfg = dict(CFG)
    cfg['pagination'] = None
    monkeypatch.setattr('crawler_discover.fetch_page',
                        _make_fetch({cfg['list_url']: PAGE1_HTML}))

    links = discover_links(cfg)
    # 3 条有效公告（导航被过滤、短标题被过滤）
    assert len(links) == 3
    assert links[0]['title'] == '某单位2026年公开招聘公告一'
    assert links[0]['date'] == '2026-06-15'
    assert links[0]['url'] == 'https://example.com/list/202606/t20260615_100001.html'


def test_discover_links_pagination_stops_on_repeat(monkeypatch):
    cfg = dict(CFG)
    cfg['pagination'] = {'pattern': 'index_{n}.html', 'max_pages': 5}
    # 第 3 页与第 2 页完全重复 → 应停止，不再请求第 4 页
    pages = {
        'https://example.com/list/': PAGE1_HTML,
        'https://example.com/list/index_2.html': PAGE2_HTML,
        'https://example.com/list/index_3.html': PAGE2_HTML,
    }
    calls = []

    def fake_fetch(url, timeout=30, retries=3):
        calls.append(url)
        return pages.get(url)

    monkeypatch.setattr('crawler_discover.fetch_page', fake_fetch)
    links = discover_links(cfg)
    assert len(links) == 5
    # 应请求 3 页后停止（第 4、5 页不应被请求）
    assert len(calls) == 3
    assert 'index_4.html' not in calls


def test_discover_links_respects_max_links(monkeypatch):
    cfg = dict(CFG)
    cfg['max_links'] = 2
    monkeypatch.setattr('crawler_discover.fetch_page',
                        _make_fetch({cfg['list_url']: PAGE1_HTML}))
    links = discover_links(cfg)
    assert len(links) == 2


# ─── crawl_list_source（monkeypatch 全网络层）─────

def test_crawl_list_source_incremental_skip(monkeypatch, tmp_path):
    """增量模式：seen 里已有的 URL 应跳过；新增的应爬取并合并。"""
    cfg = dict(CFG)
    cfg['pagination'] = None
    cfg['max_links'] = 10

    seen_file = str(tmp_path / 'seen_urls.json')
    monkeypatch.setattr('crawler_discover._load_seen',
                        lambda: {'https://example.com/list/202606/t20260615_100001.html'})
    monkeypatch.setattr('crawler_discover._save_seen', lambda seen: None)
    monkeypatch.setattr('crawler_discover.fetch_page',
                        _make_fetch({cfg['list_url']: PAGE1_HTML}))
    monkeypatch.setattr('crawler_discover.crawl_job_detail',
                        lambda url, source, partial_meta=None: {
                            'title': partial_meta.get('title', ''),
                            'url': url,
                            'publish_date': partial_meta.get('publish_date', ''),
                            'content': '内容',
                            'category': '事业单位',
                            'source': source,
                            'quality': 'ok',
                        })

    merged = []

    def fake_save(new_data):
        merged.extend(new_data)

    monkeypatch.setattr('crawler_discover.save_and_merge', fake_save)

    stats = crawl_list_source(cfg, use_seen=True)
    assert stats['discovered'] == 3
    assert stats['new'] == 2       # 1 条已 seen 跳过
    assert stats['skipped'] == 1
    assert len(merged) == 2


def test_crawl_list_source_health_when_no_links(monkeypatch):
    """列表页抓不到任何链接 → status 应为 warn。"""
    cfg = dict(CFG)
    cfg['pagination'] = None
    monkeypatch.setattr('crawler_discover.fetch_page', lambda *a, **k: None)
    stats = crawl_list_source(cfg, use_seen=True)
    assert stats['discovered'] == 0
    assert stats['status'] == 'warn'


# ─── LIST_SOURCES 配置合法性 ──────────────────────

REQUIRED_FIELDS = ('name', 'source', 'category', 'list_url', 'title_min_len', 'max_links')


def test_list_sources_required_fields():
    for cfg in LIST_SOURCES:
        for field in REQUIRED_FIELDS:
            assert field in cfg, f"源 {cfg.get('name', '?')} 缺少字段 {field}"
        assert cfg['list_url'].startswith('http'), cfg['name']
        assert cfg['title_min_len'] >= 1, cfg['name']
        assert cfg['max_links'] >= 1, cfg['name']


def test_list_sources_regex_compilable():
    for cfg in LIST_SOURCES:
        if 'url_regex' in cfg:
            re.compile(cfg['url_regex'])  # 编译失败会抛异常
        pagination = cfg.get('pagination')
        if pagination:
            assert '{n}' in pagination['pattern'], cfg['name']
            assert pagination['max_pages'] >= 1, cfg['name']


def test_list_sources_no_duplicate_names():
    names = [c['name'] for c in LIST_SOURCES]
    assert len(names) == len(set(names))
