import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

DELAY = 1

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

REGIONS = [
    '北京', '天津', '河北', '山西', '内蒙古',
    '辽宁', '吉林', '黑龙江',
    '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东',
    '河南', '湖北', '湖南', '广东', '广西', '海南',
    '重庆', '四川', '贵州', '云南', '西藏',
    '陕西', '甘肃', '青海', '宁夏', '新疆',
    '台湾', '香港', '澳门',
]

REGIONS_MAP = {r: r for r in REGIONS}

OUTPUT_FILES = {
    "all_jobs": os.path.join(DATA_DIR, "all_jobs.json"),
    "central_gov": os.path.join(DATA_DIR, "central_gov_jobs_full.json"),
}
