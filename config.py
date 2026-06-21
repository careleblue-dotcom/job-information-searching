import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

DELAY = 1

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
