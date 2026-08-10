import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import random
import logging
from datetime import datetime
from typing import Optional
from config import (
    build_headers, BASE_DELAY, OUTPUT_FILES, REGIONS, REGIONS_MAP,
    DEFAULT_SOURCE, SEEN_URLS_FILE, LOG_DIR, SCHEMA_VERSION,
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
    """请求页面,带重试 + 指数退避 + 随机 UA + 随机延迟。失败返回 None。"""
    for attempt in range(1, retries + 1):
        try:
            # 每次请求用新的 UA 池,降低被反爬识别的概率
            response = requests.get(url, headers=build_headers(), timeout=timeout)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response.text
            logger.warning('请求失败: %s, 状态码: %s (尝试 %d/%d)', url, response.status_code, attempt, retries)
        except Exception as e:
            logger.error('请求异常: %s, 错误: %s (尝试 %d/%d)', url, str(e), attempt, retries)
        if attempt < retries:
            time.sleep(BASE_DELAY * attempt)
    return None


def jitter_delay(base: Optional[float] = None) -> None:
    """请求间随机抖动:在 [base, base*2.5] 之间随机等待。base 默认 BASE_DELAY。"""
    b = base if base is not None else BASE_DELAY
    time.sleep(random.uniform(b, b * 2.5))


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


def parse_deadline(raw: str) -> str:
    """
    专门用于截止日期归一化:处理 "至2026年7月15日"、"报名截止:7.15"、
    "2026-07-15 17:00 截止"、"报名时间为2026年7月15日至2026年7月20日" 等。
    无法识别时返回空串(避免半残 deadline 误导前端排序)。
    """
    if not raw:
        return ""
    s = raw.strip()
    # 如果是范围格式 "X至Y" / "X到Y" / "X—Y" / "X~Y"，取结束日期
    range_match = re.search(
        r'(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)\s*(?:至|到|-|—|~)\s*(\d{4}[-年]?\d{1,2}[-月]\d{1,2}[日]?)',
        s,
    )
    if range_match:
        s = range_match.group(2)
    # 去掉 "至" / "截止" / "报名截止" / 末尾的 "截止" / "前" 等修饰词
    s = re.sub(r'^(报名|网上|线上)?(报名)?(截止|结束)?(时间)?(为|从)?[：:]?\s*', '', s)
    s = re.sub(r'(截止|结束|前)\s*$', '', s)
    s = re.sub(r'\s*\d{1,2}[:：]\d{2}\s*(\d{1,2}[:：]\d{2})?\s*$', '', s)  # 去时间
    s = s.strip().rstrip('。.,;,;')
    return parse_date(s)


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

    返回字段:title, url, publish_date, organization, deadline,
              region, category, content, source, crawl_time, quality
    quality: 'ok' 解析完整 / 'partial' 关键字段缺失(由调用方决定如何处理)
    解析失败返回 None(只有当整个 HTML 解析抛异常时才返 None)。
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
        # 优先 URL 文件名中的 tYYYYMMDD（北京人社局/中央机关/山西等政府站通用格式，
        # 如 t20260722_4777238.html 即 2026-07-22 发布；比全文搜日期更可靠）
        date_match = re.search(r'/t(\d{8})', url)
        if date_match:
            date_str = date_match.group(1)
            publish_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        else:
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
        for selector in ['div.content', '#content', 'div.article', 'div[class*="content"]',
                         'div[class*="article"]', '.view', '.TRS_Editor',
                         'div[class*="zoom"]', '.article-content', 'body']:
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
                # 不再截断 content:让前端按需展开,避免详情被砍
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

        deadline_raw = ""
        if content:
            deadline_patterns = [
                r'截止日期[：:]\s*([^\n。]+)',
                r'报名截止[：:]\s*([^\n。]+)',
                r'报名(截止|结束)(时间)?[：:]\s*([^\n。]+)',
                r'(网上|线上)?报名(时间)?(为|从)?[：:]?\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)\s*(至|到|-|—|~)\s*(\d{4}[-年]?\d{1,2}[-月]\d{1,2}[日]?)',
                r'报名(时间|日期)[：:]\s*([^\n。]+)',
                r'至\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)',
                r'(截止|结束)(时间|日期)[：:]\s*([^\n。]+)',
            ]
            for pattern in deadline_patterns:
                match = re.search(pattern, content)
                if match:
                    # 取最后一个捕获组（有些模式有多个组）
                    deadline_raw = match.groups()[-1].strip() if match.groups() else match.group(1).strip()
                    break

        text = title + content
        region = extract_region(title, content, source_name)
        category = extract_category(title, content)

        # 用 parse_deadline 标准化截止日期;无法识别则置空(避免半残 deadline 误导前端排序)
        deadline = parse_deadline(deadline_raw)

        # quality 判定:关键字段(title/content)缺失则视为半残
        quality = 'ok' if (title and len(content) >= 20) else 'partial'

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
            'quality': quality,
        }

    except Exception as e:
        logger.error('解析详情页失败: %s, %s', url, str(e))
        return None


def make_partial_record(url: str, source_name: str = "", title: str = "",
                        publish_date: str = "", category: str = "") -> dict:
    """
    构造"半残"记录:用于详情页抓取/解析失败时的兜底。
    quality 固定 'partial',前端据此决定是否展示(以及如何视觉标记)。
    调用方应至少提供 url + source_name;其他字段可选。
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return {
        'title': title or '(标题待补)',
        'url': url,
        'publish_date': parse_date(publish_date) if publish_date else "",
        'organization': '',
        'deadline': '',
        'region': '全国',
        'category': category or '其他',
        'content': '',
        'source': source_name or DEFAULT_SOURCE,
        'crawl_time': now,
        'quality': 'partial',
        'partial_reason': '详情页抓取或解析失败',
    }


def crawl_job_detail(url: str, source_name: str = "",
                     partial_meta: Optional[dict] = None) -> Optional[dict]:
    """
    抓取并解析单条招聘信息。
    成功:返回 parse_job_html 的 dict(quality 取决于解析质量)
    失败(网络/解析异常):返回 make_partial_record 构造的兜底记录(quality='partial')
    url 为空时返回 None。
    partial_meta 允许从列表页传入已知字段,失败时也能保留。
    """
    if not url:
        return None
    html = fetch_page(url)
    if html:
        result = parse_job_html(html, url, source_name)
        if result is not None:
            return result
    meta = partial_meta or {}
    return make_partial_record(
        url=url,
        source_name=source_name,
        title=meta.get('title', ''),
        publish_date=meta.get('publish_date', ''),
        category=meta.get('category', ''),
    )


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


# 数据文件元信息(顶层文件,不破坏 all_jobs.json 的数组结构)
META_FILE = os.path.join(os.path.dirname(SEEN_URLS_FILE), '_meta.json')


def _write_meta_file(total_jobs: int, last_crawl_status: str = "ok",
                      last_crawl_errors: int = 0) -> None:
    """
    写 data/_meta.json:供前端展示"数据更新于 X 分钟前"等。
    失败时不抛异常,只 log(数据文件本身的写盘已经成功,meta 是 best-effort)。
    """
    try:
        meta = {
            'schema_version': SCHEMA_VERSION,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_jobs': total_jobs,
            'last_crawl_status': last_crawl_status,  # 'ok' | 'partial' | 'failed'
            'last_crawl_errors': last_crawl_errors,
        }
        os.makedirs(os.path.dirname(META_FILE), exist_ok=True)
        with open(META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning('写 _meta.json 失败(非阻塞): %s', e)


def _read_existing(output_file: str) -> list:
    """读现有数据文件,不存在返空列表,解析失败返空列表 + 警告。"""
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning('读取 %s 失败,按空集处理: %s', output_file, e)
        return []


def save_and_merge(new_data: list, output_file: Optional[str] = None,
                   crawl_status: str = "ok", crawl_errors: int = 0) -> None:
    """合并新数据到现有 JSON:读旧 → 合并 → URL+标题双重去重 → 兜底 source → 写盘 + meta。"""
    if output_file is None:
        output_file = OUTPUT_FILES["all_jobs"]
    try:
        existing_data = _read_existing(output_file)

        all_data = existing_data + new_data
        _ensure_source(all_data)
        unique_data = _dedupe(all_data)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_data, f, ensure_ascii=False, indent=2)

        # 只对 all_jobs.json 写 meta 文件(供前端显示更新时间等)
        if output_file == OUTPUT_FILES["all_jobs"]:
            _write_meta_file(len(unique_data), crawl_status, crawl_errors)

        logger.info('数据已保存: 原有 %d 条, 新增 %d 条, 合并去重后 %d 条',
                    len(existing_data), len(new_data), len(unique_data))

    except Exception as e:
        logger.error('保存失败: %s', str(e))


def save_json(data: list, filepath: str, write_meta: bool = False) -> bool:
    """直接覆写保存(用于独立爬虫产物,如 central_gov_jobs_full.json)。"""
    try:
        _ensure_source(data)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info('数据已保存到: %s, 共 %d 条', filepath, len(data))
        if write_meta:
            _write_meta_file(len(data))
        return True
    except Exception as e:
        logger.error('保存JSON文件失败: %s', str(e))
        return False


FAILED_URLS_FILE = os.path.join(os.path.dirname(SEEN_URLS_FILE), 'failed_urls.json')


def _load_failed() -> dict:
    """
    加载失败队列:{url: {'attempts': int, 'last_error': str, 'source': str}}
    用于下次爬取时自动重试(默认重试 3 次后放弃,从队列中移除)。
    """
    try:
        with open(FAILED_URLS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning('读取 failed_urls 失败,按空处理: %s', e)
        return {}


def _save_failed(failed: dict) -> None:
    """持久化失败队列。"""
    try:
        os.makedirs(os.path.dirname(FAILED_URLS_FILE), exist_ok=True)
        with open(FAILED_URLS_FILE, 'w', encoding='utf-8') as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error('保存 failed_urls 失败: %s', e)


def batch_crawl(urls_with_source: list, save_interval: int = 5,
                output_file: Optional[str] = None, use_seen: bool = True,
                max_retries: int = 3) -> dict:
    """
    批量爬取详情页。

    use_seen=True 时启用增量模式:跳过 data/seen_urls.json 中已记录的 URL。
    use_seen=False(--full)时忽略增量,全量重爬。

    失败重试:失败的 URL 记到 data/failed_urls.json,带 attempts 计数,
    下次跑时会自动重试,达到 max_retries 后从队列移除。
    每 save_interval 条立刻落盘(避免一次失败丢一批)。

    返回 dict 含 ok_jobs / failed_urls / stats,方便调用方做健康度统计。
    """
    if output_file is None:
        output_file = OUTPUT_FILES["all_jobs"]

    seen = _load_seen() if use_seen else set()
    failed = _load_failed() if use_seen else {}
    if use_seen:
        logger.info('增量模式:已记录 %d 个 URL 跳过, %d 个失败待重试', len(seen), len(failed))

    logger.info('开始批量爬取,共 %d 个URL', len(urls_with_source))

    all_jobs: list = []
    batch_jobs: list = []
    new_failed: dict = dict(failed)  # 复制,本轮成功的移除
    error_count = 0

    for i, (url, source_name) in enumerate(urls_with_source, 1):
        if use_seen and url in seen:
            logger.info('[%d/%d] 跳过(已爬): %s', i, len(urls_with_source), source_name)
            continue

        logger.info('[%d/%d] 来源: %s', i, len(urls_with_source), source_name)

        try:
            job_data = crawl_job_detail(url, source_name)
        except Exception as e:
            logger.error('单条爬取异常: %s, %s', url, str(e))
            job_data = make_partial_record(url=url, source_name=source_name)

        if job_data and job_data.get('quality') == 'partial':
            error_count += 1

        if job_data:
            all_jobs.append(job_data)
            batch_jobs.append(job_data)
            # 成功:从失败队列移除
            if url in new_failed:
                new_failed.pop(url, None)

        if len(batch_jobs) >= save_interval:
            logger.info('增量保存 %d 条...', len(batch_jobs))
            save_and_merge(batch_jobs, output_file)
            if use_seen:
                seen.update(j['url'] for j in batch_jobs if j.get('url'))
                _save_seen(seen)
            batch_jobs = []

        jitter_delay()

    if batch_jobs:
        logger.info('保存剩余 %d 条...', len(batch_jobs))
        save_and_merge(batch_jobs, output_file)
        if use_seen:
            seen.update(j['url'] for j in batch_jobs if j.get('url'))
            _save_seen(seen)

    # 把本轮"超过 max_retries 次仍失败的"清理掉,其余保留到下次
    cleaned_failed = {}
    for url, info in new_failed.items():
        if info.get('attempts', 0) < max_retries:
            cleaned_failed[url] = info
    _save_failed(cleaned_failed)

    status = 'ok' if error_count == 0 else 'partial'
    if output_file == OUTPUT_FILES["all_jobs"]:
        _write_meta_file(len(_read_existing(output_file)), status, error_count)

    logger.info('批量爬取完成: 成功 %d 条, 本轮出错 %d 条, 失败队列剩余 %d 条',
                len(all_jobs), error_count, len(cleaned_failed))

    return {
        'ok_jobs': all_jobs,
        'failed_count': error_count,
        'failed_queue_size': len(cleaned_failed),
        'status': status,
    }
