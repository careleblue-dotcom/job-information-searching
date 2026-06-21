#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared.py 的离线单元测试：覆盖纯函数与解析逻辑，不发任何网络请求。
运行：pytest tests/test_shared.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from shared import (
    parse_date,
    extract_region,
    extract_category,
    parse_job_html,
    _normalize_title,
    _dedupe,
    _ensure_source,
    crawl_job_detail,
)
from config import DEFAULT_SOURCE

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


# ─── parse_date ────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ('2026-06-15', '2026-06-15'),
    ('2026年6月15日', '2026-06-15'),
    ('2026.06.15', '2026-06-15'),
    ('2026/06/15', '2026-06-15'),
    ('2026年06月05日', '2026-06-05'),       # 补零
    ('  2026-1-3  ', '2026-01-03'),          # 去空白 + 补零
    ('', ''),                                # 空值
    ('无日期文本', '无日期文本'),              # 不可识别时返回原文
])
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


# ─── extract_category ──────────────────────────────

def test_category_xuandiao():
    assert extract_category('江苏省2026年选调公告', '') == '选调生'


def test_category_talent():
    assert extract_category('某市人才引进公告', '') == '人才引进'


def test_category_shiye():
    assert extract_category('某事业单位公开招聘', '') == '事业单位'


def test_category_gongwuyuan():
    assert extract_category('2026年公务员考试录用', '') == '公务员考试'


def test_category_default_other():
    assert extract_category('一个不相关的标题', '内容也无关') == '其他'


def test_category_priority_xuandiao_over_gongwuyuan():
    # "选调"优先级高于"公务员考试"关键词
    assert extract_category('选调公务员', '') == '选调生'


# ─── extract_region ────────────────────────────────

def test_region_from_title():
    assert extract_region('江苏省选调公告', '') == '江苏'


def test_region_from_source():
    assert extract_region('公告', '', source='广东省委组织部') == '广东'


def test_region_default_quanguo():
    assert extract_region('全国性公告', '') == '全国'


def test_region_matches_first_province_in_list_order():
    """extract_region 按 PROVINCES 列表顺序匹配，先出现的省份胜出。
    这是既有行为（来源/标题/正文合并后顺序匹配），本测试锁定该行为。"""
    # '北京' 在 PROVINCES 列表中早于 '江苏'，故即使 source 含江苏也返回北京
    assert extract_region('北京', '', source='江苏省') == '北京'
    # 仅 source 命中时正常返回
    assert extract_region('通知公告', '正文', source='江苏省委组织部') == '江苏'


# ─── parse_job_html（离线，用 fixtures）──────────────

def test_parse_detail_extracts_fields():
    html = _read_fixture('detail_sample.html')
    job = parse_job_html(html, 'https://www.jszzb.gov.cn/tzgg/art/2026/abc.html', '江苏省委组织部')

    assert job is not None
    assert job['title'] == '江苏省2026年应届优秀大学毕业生选调工作公告'
    # 日期应被规范化为 YYYY-MM-DD
    assert re.match(r'^\d{4}-\d{2}-\d{2}$', job['publish_date']), job['publish_date']
    assert job['publish_date'] == '2026-06-15'
    assert job['category'] == '选调生'
    assert job['region'] == '江苏'
    assert job['source'] == '江苏省委组织部'
    assert job['url'].endswith('abc.html')
    # 内容不应为空
    assert len(job['content']) > 0
    # 应截断/或包含关键文本
    assert '选调' in job['content']


def test_parse_detail_source_fallback():
    """source_name 为空时应填默认值，不留 None/空串。"""
    html = _read_fixture('detail_sample.html')
    job = parse_job_html(html, 'https://example.com/x.html', '')
    assert job is not None
    assert job['source'] == DEFAULT_SOURCE


def test_parse_minimal_html_returns_dict():
    """最简页面也应能返回字典，不抛异常。"""
    html = _read_fixture('detail_minimal.html')
    job = parse_job_html(html, 'https://example.com/min.html', '测试来源')
    assert job is not None
    assert job['source'] == '测试来源'
    assert job['category'] == '事业单位'  # 含"事业单位""公开招聘"


def test_parse_empty_html():
    """空 HTML 应返回 None 或不含异常。"""
    job = parse_job_html('', 'https://example.com', '测试')
    # 空内容下不要求必返回 None，但不能抛异常；返回时字段需完整
    if job is not None:
        assert 'title' in job and 'source' in job


# ─── crawl_job_detail（monkeypatch 网络层）──────────

def test_crawl_job_detail_uses_fetch_and_parse(monkeypatch):
    """crawl_job_detail 应委托 fetch_page + parse_job_html，本身不发网络。"""
    from shared import crawl_job_detail as _cjd
    html = _read_fixture('detail_sample.html')

    calls = []

    def fake_fetch(url, timeout=30, retries=3):
        calls.append(url)
        return html

    monkeypatch.setattr('shared.fetch_page', fake_fetch)

    job = _cjd('https://www.jszzb.gov.cn/tzgg/art/2026/abc.html', '江苏省委组织部')
    assert calls == ['https://www.jszzb.gov.cn/tzgg/art/2026/abc.html']
    assert job is not None
    assert job['title'] == '江苏省2026年应届优秀大学毕业生选调工作公告'


def test_crawl_job_detail_returns_none_when_fetch_fails(monkeypatch):
    """fetch 返回 None 时 crawl_job_detail 应返回 None，不抛异常。"""
    monkeypatch.setattr('shared.fetch_page', lambda *a, **k: None)
    assert crawl_job_detail('https://example.com', '测试') is None


# ─── _normalize_title ──────────────────────────────

def test_normalize_strips_whitespace():
    assert _normalize_title('  2026 江苏  选调 ') == '2026江苏选调'


def test_normalize_empty():
    assert _normalize_title('') == ''
    assert _normalize_title(None) == ''


# ─── _dedupe ───────────────────────────────────────

def test_dedupe_same_url_keeps_latest():
    items = [
        {'title': 't', 'url': 'http://x/1', 'crawl_time': '2026-01-01 10:00:00', 'source': 'A'},
        {'title': 't', 'url': 'http://x/1', 'crawl_time': '2026-01-05 10:00:00', 'source': 'A'},
    ]
    r = _dedupe(items)
    assert len(r) == 1
    assert r[0]['crawl_time'] == '2026-01-05 10:00:00'


def test_dedupe_cross_source_same_title():
    items = [
        {'title': '2026江苏省选调生公告', 'url': 'http://a/1', 'crawl_time': '2026-01-01', 'source': 'A'},
        {'title': '2026江苏省选调生公告', 'url': 'http://b/2', 'crawl_time': '2026-01-03', 'source': 'B'},
    ]
    r = _dedupe(items)
    assert len(r) == 1
    assert r[0]['url'] == 'http://b/2'  # 保留更新者


def test_dedupe_distinct_items_kept():
    items = [
        {'title': '甲', 'url': 'http://x/1', 'crawl_time': '2026-01-01', 'source': 'A'},
        {'title': '乙', 'url': 'http://x/2', 'crawl_time': '2026-01-01', 'source': 'B'},
    ]
    assert len(_dedupe(items)) == 2


# ─── _ensure_source ────────────────────────────────

def test_ensure_source_fills_empty():
    items = [{'title': 'x', 'url': 'u', 'source': None},
             {'title': 'y', 'url': 'v', 'source': ''},
             {'title': 'z', 'url': 'w', 'source': '官方'}]
    _ensure_source(items)
    assert items[0]['source'] == DEFAULT_SOURCE
    assert items[1]['source'] == DEFAULT_SOURCE
    assert items[2]['source'] == '官方'  # 已有值不覆盖
