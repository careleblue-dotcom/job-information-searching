import os
import random

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

# UA 池:每次请求随机选一个,降低被反爬识别的概率。
# 用近 2 年内主流浏览器版本,避免太老被风控。
USER_AGENT_POOL = [
    # Chrome (Windows)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    # Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
]


def build_headers() -> dict:
    """每次请求生成一组随机 UA 的 headers。集中一处方便测试 mock。"""
    return {
        'User-Agent': random.choice(USER_AGENT_POOL),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }


# 旧名 HEADERS 保留兼容(只取第一项 UA,用于单次请求的简单场景)
HEADERS = build_headers()

# 基础请求延迟(秒),实际值会在 [BASE_DELAY, BASE_DELAY * 2.5] 区间内随机抖动
BASE_DELAY = 1.0
DELAY = BASE_DELAY  # 旧名兼容

# 数据文件 schema 版本号:当字段定义有破坏性变更时 +1,前端可据此做兼容处理
SCHEMA_VERSION = 2

# 省份/地区表：单一数据源（shared.py 与 cleanup.py 共用，避免两处不一致）
# 直接列出"省/直辖市/自治区/特别行政区"的简称，长度 2-3 字，与标题/正文做包含匹配
PROVINCES = [
    '北京', '天津', '河北', '山西', '内蒙古',
    '辽宁', '吉林', '黑龙江',
    '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东',
    '河南', '湖北', '湖南', '广东', '广西', '海南',
    '重庆', '四川', '贵州', '云南', '西藏',
    '陕西', '甘肃', '青海', '宁夏', '新疆',
    '台湾', '香港', '澳门',
]

# 保留旧名作为别名，兼容现有代码（crawler_*.py 里有 from config import ... REGIONS）
REGIONS = PROVINCES
REGIONS_MAP = {r: r for r in PROVINCES}

# source 字段为空时的兜底值（避免前端按来源筛选时丢数据）
DEFAULT_SOURCE = '未知来源'

# 增量爬取状态文件：记录已爬取的 URL，避免重复抓取
SEEN_URLS_FILE = os.path.join(DATA_DIR, "seen_urls.json")

# 中央国家机关平台配置
CENTRAL_GOV = {
    "BASE_URL": "http://114.255.111.180/SYrlzyhshbzb/fwyd/SYkaoshizhaopin/zyhgjjgsydwgkzp",
    "CATEGORIES": {
        "zpgg": "招聘信息",
        "gxbyszpzl": "高校毕业生招聘专栏",
        "zytz": "补充公告",
    },
}

# 江苏省委组织部
JSZZB = {
    "BASE_URL": "https://www.jszzb.gov.cn",
    "LIST_URL": "https://www.jszzb.gov.cn/tzgg/",
    "KEYWORDS": ['选调', '公务员', '人才引进', '编制', '党政', '遴选', '优培'],
}

OUTPUT_FILES = {
    "all_jobs": os.path.join(DATA_DIR, "all_jobs.json"),
    "central_gov": os.path.join(DATA_DIR, "central_gov_jobs_full.json"),
}


# ─── 列表页数据源配置（crawler_discover.py 使用） ─────────────────
# 每个源 = 一个公告列表页（可翻页），框架自动：抓列表 → 提取公告链接 → 增量过滤 → 爬详情。
# 字段说明：
#   name          源名（日志/报告用）
#   source        写入数据记录的 source 字段
#   category      默认分类（详情解析失败/未命中分类时的兜底）
#   list_url      列表页 URL
#   url_regex     详情页 URL 必须匹配的正则（可选，与 url_contains 二选一或并用）
#   url_contains  详情页 URL 必须包含的子串列表（可选）
#   url_excludes  详情页 URL 不能包含的子串列表（可选）
#   title_min_len 标题最短长度（过滤导航/装饰链接）
#   keywords      标题关键词白名单（None=不按关键词过滤）
#   max_links     单源本轮最多爬取的详情条数
#   pagination    翻页模板 {'pattern': 'index_{n}.html', 'max_pages': N}；None=不翻页。
#                 pattern 中 {n} 会被替换为页码（第 1 页用 list_url 本身）。
#                 翻页期间若新页链接与已有链接完全重复则自动提前停止。
LIST_SOURCES = [
    # ── 中央国家机关招聘平台（3 个栏目，支持翻页，最活跃源） ──
    {
        "name": "中央国家机关招聘-招聘信息",
        "source": "中央国家机关招聘平台",
        "category": "招聘信息",
        "list_url": f"{CENTRAL_GOV['BASE_URL']}/zpgg",
        "url_regex": r'/20\d{4}/t20\d{6,8}_?\d*\.html',
        "title_min_len": 6,
        "max_links": 30,
        "pagination": {"pattern": "index_{n}.html", "max_pages": 2},
    },
    {
        "name": "中央国家机关招聘-高校毕业生专栏",
        "source": "中央国家机关招聘平台",
        "category": "高校毕业生招聘专栏",
        "list_url": f"{CENTRAL_GOV['BASE_URL']}/gxbyszpzl",
        "url_regex": r'/20\d{4}/t20\d{6,8}_?\d*\.html',
        "title_min_len": 6,
        "max_links": 30,
        "pagination": {"pattern": "index_{n}.html", "max_pages": 2},
    },
    {
        "name": "中央国家机关招聘-补充公告",
        "source": "中央国家机关招聘平台",
        "category": "补充公告",
        "list_url": f"{CENTRAL_GOV['BASE_URL']}/zytz",
        "url_regex": r'/20\d{4}/t20\d{6,8}_?\d*\.html',
        "title_min_len": 6,
        "max_links": 30,
        "pagination": {"pattern": "index_{n}.html", "max_pages": 2},
    },
    # ── 北京人社局（通知公告 + 事业单位公开招聘，均支持翻页） ──
    {
        "name": "北京人社局-通知公告",
        "source": "北京市人社局",
        "category": "事业单位",
        "list_url": "https://rsj.beijing.gov.cn/xxgk/tzgg/",
        "url_regex": r'/20\d{4}/t20\d{6,8}_?\d*\.html',
        "keywords": ['招聘', '录用', '事业单位', '选调', '人才', '公务员'],
        "title_min_len": 8,
        "max_links": 25,
        "pagination": {"pattern": "index_{n}.html", "max_pages": 2},
    },
    {
        "name": "北京人社局-事业单位公开招聘",
        "source": "北京市人社局",
        "category": "事业单位",
        "list_url": "https://rsj.beijing.gov.cn/xxgk/gkzp/",
        "url_regex": r'/20\d{4}/t20\d{6,8}_?\d*\.html',
        "title_min_len": 8,
        "max_links": 25,
        "pagination": {"pattern": "index_{n}.html", "max_pages": 2},
    },
    # ── 广东省委组织部 ──
    {
        "name": "广东省委组织部-通知公告",
        "source": "广东省委组织部官网",
        "category": "招聘信息",
        "list_url": "https://www.gdzz.gov.cn/tzgg/",
        "url_regex": r'/tzgg/content/post_\d+\.html',
        "keywords": ['招聘', '选调', '录用', '人才', '遴选', '公务员'],
        "title_min_len": 8,
        "max_links": 25,
        "pagination": {"pattern": "index_{n}.html", "max_pages": 3},
    },
    # ── 山西人社厅选调专栏（无翻页） ──
    {
        "name": "山西人社厅-选调生专栏",
        "source": "山西省人社厅",
        "category": "选调生",
        "list_url": "https://rst.shanxi.gov.cn/rsks/gwyks/2026xdsks/",
        "url_regex": r'/20\d{4}/t20\d{6,8}_?\d*\.shtml',
        "title_min_len": 8,
        "max_links": 25,
        "pagination": None,
    },
    # ── 广西人事考试网选调/公务员专栏（无翻页） ──
    {
        "name": "广西人事考试网-选调公务员专栏",
        "source": "广西人事考试网",
        "category": "公务员考试",
        "list_url": "https://www.gxpta.com.cn/ksxm/gwyzlks/gx2026ndkslygwyxdszt/",
        "url_regex": r'/(20\d{2}ngwygg|20\d{2}nxdsgg)/t\d+\.html',
        "title_min_len": 8,
        "max_links": 25,
        "pagination": None,
    },
    # ── 辽宁人事考试网公务员招考公告（无翻页） ──
    {
        "name": "辽宁人事考试网-公务员招考公告",
        "source": "辽宁人事考试网",
        "category": "公务员考试",
        "list_url": "https://www.lnrsks.com/html/gwy_zhaokaogonggao/",
        "url_contains": ['/html/gwy_zhaokaogonggao/'],
        "title_min_len": 6,
        "max_links": 25,
        "pagination": None,
    },
    # ── 国务院国资委央企招聘（无翻页） ──
    {
        "name": "国务院国资委-央企招聘",
        "source": "国务院国资委",
        "category": "央企招聘",
        "list_url": "http://www.sasac.gov.cn/n2588035/n2588325/n2588350/index.html",
        "url_regex": r'/n2588035/n2588325/n2588350/c\d+/content\.html',
        "keywords": ['招聘', '校园招聘', '公开招聘', '选调'],
        "title_min_len": 5,
        "max_links": 20,
        "pagination": None,
    },
]

# 列表页源跑完后的报告文件（crawler_discover.py 输出，CI 据此判断是否需要告警）
CRAWL_REPORT_FILE = os.path.join(LOG_DIR, 'crawl_report.json')
