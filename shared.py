import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import logging
from datetime import datetime
from config import HEADERS, DELAY, OUTPUT_FILES, REGIONS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def fetch_page(url, timeout=30, retries=3):
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


def parse_date(date_str):
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


def extract_region(title, content, source=""):
    text = source + ' ' + title + ' ' + content
    for r in REGIONS:
        if r in text:
            return r
    return "全国"


def extract_category(title, content):
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


def crawl_job_detail(url, source_name=""):
    html = fetch_page(url)
    if not html:
        return None

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
            'source': source_name,
            'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    except Exception as e:
        logger.error('解析详情页失败: %s, %s', url, str(e))
        return None


def save_and_merge(new_data, output_file=None):
    if output_file is None:
        output_file = OUTPUT_FILES["all_jobs"]
    try:
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = []

        all_data = existing_data + new_data

        seen_urls = set()
        unique_data = []
        for item in all_data:
            url = item.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_data.append(item)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_data, f, ensure_ascii=False, indent=2)

        logger.info('数据已保存: 原有 %d 条, 新增 %d 条, 合并后 %d 条', len(existing_data), len(new_data), len(unique_data))

    except Exception as e:
        logger.error('保存失败: %s', str(e))


def save_json(data, filepath):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info('数据已保存到: %s, 共 %d 条', filepath, len(data))
        return True
    except Exception as e:
        logger.error('保存JSON文件失败: %s', str(e))
        return False


def batch_crawl(urls_with_source, save_interval=10, output_file=None):
    if output_file is None:
        output_file = OUTPUT_FILES["all_jobs"]
    logger.info('开始批量爬取，共 %d 个URL', len(urls_with_source))

    all_jobs = []
    batch_jobs = []

    for i, (url, source_name) in enumerate(urls_with_source, 1):
        logger.info('[%d/%d] 来源: %s', i, len(urls_with_source), source_name)

        job_data = crawl_job_detail(url, source_name)
        if job_data:
            all_jobs.append(job_data)
            batch_jobs.append(job_data)

        if len(batch_jobs) >= save_interval:
            logger.info('增量保存 %d 条...', len(batch_jobs))
            save_and_merge(batch_jobs, output_file)
            batch_jobs = []

        time.sleep(DELAY)

    if batch_jobs:
        logger.info('保存剩余 %d 条...', len(batch_jobs))
        save_and_merge(batch_jobs, output_file)

    logger.info('批量爬取完成，共 %d 条', len(all_jobs))
    return all_jobs
