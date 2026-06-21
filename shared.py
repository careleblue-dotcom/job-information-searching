import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import logging
from datetime import datetime
from typing import Optional
from config import (
    HEADERS, DELAY, OUTPUT_FILES, REGIONS, REGIONS_MAP,
    DEFAULT_SOURCE, SEEN_URLS_FILE, LOG_DIR,
)

# ─── 日志：控制台 + 文件双输出 ────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    _console = logging.StreamHandler()
    _console.setFormatter(_fmt)
    logger.addHandler(_console)
    try:
        _file = logging.FileHandler(os.path.join(LOG_DIR, 'crawler.log'), encoding='utf-8')
        _file.setFormatter(_fmt)
        logger.addHandler(_file)
    except Exception:
        # 文件 handler 失败不应阻断运行
        pass


def fetch_page(url: str, timeout: int = 30, retries: int = 3) -> Optional[str]:
    """请求页面，带重试与指数退避。失败返回 None。"""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response.text
            logger.warning('请求失败: %s, 状态码: %s (尝试 %d/%d)', url, response.status_code, attempt, retries)
        except Exception as e:
            logger.error('请求异常: %s, 错误: %s (尝试 %d/%d)', url, str(e), attempt, retries)
        if attempt < retries:
            time.sleep(DELAY * attempt)
    return None


def parse_date(date_str: str) -> str:
    """把多种日期格式统一成 YYYY-MM-DD。无法识别时返回原文（去空白）。"""
    if not date_str:
        return ""
    try:
        formats = [
            '%Y-%m-%d',
            '%Y年%m月%d日',
            '%Y.%m.%d',
            '%Y/%m/%d',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        match = re.search(r'(\d{4})[-年.](\d{1,2})[-月.](\d{1,2})', date_str)
        if match:
            return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
        return date_str.strip()
    except Exception:
        return date_str.strip()


def extract_region(title: str, content: str, source: str = "") -> str:
    """从标题/正文/来源中匹配省份，匹配不到返回"全国"。"""
    text = source + ' ' + title + ' ' + content
    for r in REGIONS:
        if r in text:
            return r
    return "全国"


def extract_category(title: str, content: str) -> str:
    """按关键词命中优先级归类。"""
    combined = title + ' ' + content
    if '选调' in combined:
        return '选调生'
    if '人才引进' in combined:
        return '人才引进'
    if any(kw in combined for kw in ['事业单位', '公开招聘', '编制', '招聘简章']):
        return '事业单位'
    if any(kw in combined for kw in ['公务员考试', '国考', '省考', '招录考试', '录用']):
        return '公务员考试'
    if any(kw in combined for kw in ['高校毕业生', '应届毕业生', '校园招聘', '毕业生招聘']):
        return '高校毕业生招聘专栏'
    if any(kw in combined for kw in ['补充公告', '更正公告', '调整公告', '递补']):
        return '补充公告'
    if any(kw in combined for kw in ['招聘', '招录', '招考']):
        return '招聘信息'
    return '其他'


def parse_job_html(html: str, url: str, source_name: str = "") -> Optional[dict]:
    """
    纯解析函数：从已抓取的 HTML 解析一条招聘信息。
    不做任何网络请求，便于单元测试（传入 fixtures 内容即可）。

    返回字段：title, url, publish_date, organization, deadline,
              region, category, content, source, crawl_time
    解析失败返回 None。
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')

        title = ""
        for selector in ['h1', 'h2', 'h3', '.title', '#title', 'div[class*="title"]',
                         'meta[property="og:title"]', 'title', '.article-title', '#ArticleTitle']:
            if selector.startswith('meta'):
                elem = soup.select_one(selector)
                if elem:
                    title = elem.get('content', '').strip()
                    if title:
                        break
            elif selector == 'title':
                elem = soup.select_one(selector)
                if elem:
                    title = elem.get_text(strip=True)
                    if title:
                        break
            else:
                elem = soup.select_one(selector)
                if elem:
                    title = elem.get_text(strip=True)
                    if title:
                        break

        publish_date = ""
        date_match = re.search(r'/(\d{8})/', url)
        if date_match:
            date_str = date_match.group(1)
            publish_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        if not publish_date:
            for selector in ['.date', '#date', 'span.date', 'div.date', 'p.date', '.time', '#time',
                             'meta[property="article:published_time"]', 'div[class*="date"]', 'span[class*="time"]']:
                elem = soup.select_one(selector)
                if elem:
                    if selector.startswith('meta'):
                        date_text = elem.get('content', '')
                    else:
                        date_text = elem.get_text(strip=True)
                    date_match = re.search(r'(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)', date_text)
                    if date_match:
                        publish_date = date_match.group(1)
                        break

        if not publish_date:
            date_text = soup.get_text()
            for pattern in [r'发布日期[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)',
                            r'(\d{4}年\d{1,2}月\d{1,2}日)']:
                date_match = re.search(pattern, date_text)
                if date_match:
                    publish_date = date_match.group(1)
                    break

        content = ""
        for selector in ['div.content', '#content', 'div.article', 'div[class*="content"]', 'div[class*="article"]', 'body']:
            elem = soup.select_one(selector)
            if elem:
                for tag in elem.find_all(['nav', 'aside', 'script', 'style']):
                    tag.decompose()
                content = elem.get_text(strip=True)
                if not content:
                    continue
                title_elem = elem.find(['h1', 'h2', 'h3'])
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    title_pos = content.find(title_text)
                    if title_pos >= 0:
                        content = content[title_pos:]
                if len(content) > 500:
                    content = content[:500] + "..."
                break

        organization = ""
        if content:
            org_patterns = [
                r'招聘单位[：:]\s*([^\n。]+)',
                r'用人单位[：:]\s*([^\n。]+)',
                r'([\u4e00-\u9fa5]+)2026年度公开招聘',
                r'(中共[^省]*省委组织部|[^省]*省委组织部)',
            ]
            for pattern in org_patterns:
                match = re.search(pattern, content)
                if match:
                    organization = match.group(1).strip()
                    break

        deadline = ""
        if content:
            deadline_patterns = [
                r'截止日期[：:]\s*([^\n。]+)',
                r'报名截止[：:]\s*([^\n。]+)',
                r'至\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)',
            ]
            for pattern in deadline_patterns:
                match = re.search(pattern, content)
                if match:
                    deadline = match.group(1).strip()
                    break

        text = title + content
        region = extract_region(title, content, source_name)
        category = extract_category(title, content)

        return {
            'title': title,
            'url': url,
            'publish_date': parse_date(publish_date) if publish_date else "",
            'organization': organization,
            'deadline': deadline,
            'region': region,
            'category': category,
            'content': content,
            'source': source_name or DEFAULT_SOURCE,
            'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    except Exception as e:
        logger.error('解析详情页失败: %s, %s', url, str(e))
        return None


def crawl_job_detail(url: str, source_name: str = "") -> Optional[dict]:
    """抓取并解析单条招聘信息。对外签名与返回值不变，内部委托给 parse_job_html。"""
    html = fetch_page(url)
    if not html:
        return None
    return parse_job_html(html, url, source_name)


def _normalize_title(title: str) -> str:
    """标题归一化：去空白与常见标点差异，用于跨源去重比较。"""
    if not title:
        return ""
    return re.sub(r'[\s\u3000]+', '', title).strip()


def _dedupe(items: list) -> list:
    """
    统一去重：先按 URL 去重，再按归一化标题去重（同一标题不同 URL 视为重复）。
    冲突时保留 crawl_time 最新的一条；无 crawl_time 时保留先出现的。
    返回去重后的新列表（保持原顺序）。
    """
    # 第一遍：按 URL 去重，保留最新
    by_url: dict = {}
    for item in items:
        url = item.get('url', '')
        if not url:
            continue
        prev = by_url.get(url)
        if prev is None or _crawl_time_of(item) >= _crawl_time_of(prev):
            by_url[url] = item

    # 第二遍：按归一化标题去重，保留最新
    by_title: dict = {}
    no_title: list = []
    for item in by_url.values():
        norm = _normalize_title(item.get('title', ''))
        if not norm:
            no_title.append(item)
            continue
        prev = by_title.get(norm)
        if prev is None or _crawl_time_of(item) >= _crawl_time_of(prev):
            by_title[norm] = item

    # 保持原相对顺序
    keep_ids = set(id(v) for v in by_title.values()) | set(id(v) for v in no_title)
    return [item for item in items if id(item) in keep_ids]


def _crawl_time_of(item: dict) -> str:
    return item.get('crawl_time') or ''


def _ensure_source(items: list) -> list:
    """source 为空/None 时填默认值，避免前端按来源筛选丢数据。"""
    for item in items:
        if not item.get('source'):
            item['source'] = DEFAULT_SOURCE
    return items


def _load_seen() -> set:
    """加载已爬 URL 集合，用于增量爬取。文件不存在返回空集。"""
    try:
        with open(SEEN_URLS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set(data.keys())
    except FileNotFoundError:
        return set()
    except Exception as e:
        logger.warning('读取 seen_urls 失败，按空集处理: %s', e)
        return set()


def _save_seen(seen: set) -> None:
    """持久化已爬 URL 集合。"""
    try:
        os.makedirs(os.path.dirname(SEEN_URLS_FILE), exist_ok=True)
        with open(SEEN_URLS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(seen), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error('保存 seen_urls 失败: %s', e)


def save_and_merge(new_data: list, output_file: Optional[str] = None) -> None:
    """合并新数据到现有 JSON：读旧 → 合并 → URL+标题双重去重 → 兜底 source → 写盘。"""
    if output_file is None:
        output_file = OUTPUT_FILES["all_jobs"]
    try:
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = []

        all_data = existing_data + new_data
        _ensure_source(all_data)
        unique_data = _dedupe(all_data)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_data, f, ensure_ascii=False, indent=2)

        logger.info('数据已保存: 原有 %d 条, 新增 %d 条, 合并去重后 %d 条',
                    len(existing_data), len(new_data), len(unique_data))

    except Exception as e:
        logger.error('保存失败: %s', str(e))


def save_json(data: list, filepath: str) -> bool:
    """直接覆写保存（用于独立爬虫产物，如 central_gov_jobs_full.json）。"""
    try:
        _ensure_source(data)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info('数据已保存到: %s, 共 %d 条', filepath, len(data))
        return True
    except Exception as e:
        logger.error('保存JSON文件失败: %s', str(e))
        return False


def batch_crawl(urls_with_source: list, save_interval: int = 10,
                output_file: Optional[str] = None, use_seen: bool = True) -> list:
    """
    批量爬取详情页。

    use_seen=True 时启用增量模式：跳过 data/seen_urls.json 中已记录的 URL，
    本次成功的 URL 会追加写入，避免重复抓取。
    use_seen=False（--full）时忽略增量，全量重爬。
    """
    if output_file is None:
        output_file = OUTPUT_FILES["all_jobs"]

    seen = _load_seen() if use_seen else set()
    if use_seen:
        logger.info('增量模式：已记录 %d 个 URL，将跳过', len(seen))

    logger.info('开始批量爬取，共 %d 个URL', len(urls_with_source))

    all_jobs: list = []
    batch_jobs: list = []

    for i, (url, source_name) in enumerate(urls_with_source, 1):
        if use_seen and url in seen:
            logger.info('[%d/%d] 跳过(已爬): %s', i, len(urls_with_source), source_name)
            continue

        logger.info('[%d/%d] 来源: %s', i, len(urls_with_source), source_name)

        job_data = crawl_job_detail(url, source_name)
        if job_data:
            all_jobs.append(job_data)
            batch_jobs.append(job_data)

        if len(batch_jobs) >= save_interval:
            logger.info('增量保存 %d 条...', len(batch_jobs))
            save_and_merge(batch_jobs, output_file)
            if use_seen:
                seen.update(j['url'] for j in batch_jobs if j.get('url'))
                _save_seen(seen)
            batch_jobs = []

        time.sleep(DELAY)

    if batch_jobs:
        logger.info('保存剩余 %d 条...', len(batch_jobs))
        save_and_merge(batch_jobs, output_file)
        if use_seen:
            seen.update(j['url'] for j in batch_jobs if j.get('url'))
            _save_seen(seen)

    logger.info('批量爬取完成，共 %d 条', len(all_jobs))
    return all_jobs
