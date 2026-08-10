#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测候选列表源的可用性与链接提取效果（只读，不写数据、不爬详情）。

用法: python scripts/probe_sources.py [--all]
默认只探测当前未接入的候选源; --all 连已接入的活源一起探测做对比。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from shared import fetch_page

# 探测结果同时写入本文件（UTF-8），避免 Windows 控制台 GBK 显示中文乱码
RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'probe_result.txt')

CANDIDATES = [
    # 未接入的候选源（重点探测）
    {"name": "山西人社厅选调专栏", "url": "https://rst.shanxi.gov.cn/rsks/gwyks/2026xdsks/"},
    {"name": "广西人事考试网选调专栏", "url": "https://www.gxpta.com.cn/ksxm/gwyzlks/gx2026ndkslygwyxdszt/"},
    {"name": "北京人社局通知公告", "url": "https://rsj.beijing.gov.cn/xxgk/tzgg/"},
    {"name": "辽宁人事考试网公务员公告", "url": "https://www.lnrsks.com/html/gwy_zhaokaogonggao/"},
    {"name": "青海人事考试网", "url": "http://www.qhpta.com/"},
    {"name": "内蒙古人事考试网", "url": "http://www.impta.com.cn/"},
    {"name": "安徽人事考试网公告", "url": "https://www.apta.gov.cn/Officer/FAnnouncement"},
    {"name": "高校人才网公告", "url": "https://www.gaoxiaojob.com/announcement/"},
    {"name": "湖南红网", "url": "https://www.hxw.gov.cn/"},
    {"name": "黑龙江教育厅通知", "url": "https://jyt.hlj.gov.cn/jyt/c110476/list.shtml"},
    {"name": "国家大学生就业服务平台", "url": "https://www.ncss.cn/student/jobs/"},
    # 新增候选源（用户操作示例）
    {"name": "四川人事考试网-公务员考试", "url": "https://www.scpta.com.cn/front/News/column?parentId=1003001"},
    {"name": "四川人事考试网-首页", "url": "https://www.scpta.com.cn/"},
    {"name": "贵州人事考试信息网", "url": "https://www.gzpta.gov.cn/"},
    {"name": "重庆人事考试网", "url": "https://www.cqpa.gov.cn/"},
    {"name": "河南省人事考试中心", "url": "https://www.hnrsks.com/"},
    {"name": "江西省人事考试网", "url": "http://www.jxpta.com/"},
    {"name": "河北省人事考试网", "url": "https://www.hebpta.com.cn/"},
    # 已接入的活源（对比基准）
    {"name": "中央国家机关招聘平台zpgg", "url": "http://114.255.111.180/SYrlzyhshbzb/fwyd/SYkaoshizhaopin/zyhgjjgsydwgkzp/zpgg"},
    {"name": "江苏省委组织部", "url": "https://www.jszzb.gov.cn/tzgg/"},
    {"name": "广东组织工作网", "url": "https://www.gdzz.gov.cn/tzgg/"},
    {"name": "中国公共招聘网", "url": "http://www.job.mohrss.gov.cn/qyzp/index.jhtml"},
    {"name": "国务院国资委", "url": "http://www.sasac.gov.cn/n2588035/n2588325/n2588350/index.html"},
]

NOISE_KEYWORDS = ('首页', '上一页', '下一页', '尾页', '登录', '注册', '网站声明',
                  '收藏本站', '设为首页', '联系我们', '无障碍', 'English', '返回')


def probe(url: str) -> dict:
    html = fetch_page(url, timeout=15, retries=1)
    if not html:
        return {"status": "FETCH_FAIL", "html_len": 0, "total_a": 0, "samples": []}
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=True)
    samples = []
    for a in links:
        text = a.get_text(strip=True)
        href = a.get('href', '')
        if len(text) < 8:
            continue
        if any(k in text for k in NOISE_KEYWORDS):
            continue
        samples.append({"text": text[:44], "href": href[:90]})
        if len(samples) >= 10:
            break
    return {"status": "OK", "html_len": len(html), "total_a": len(links), "samples": samples}


def _judge(r: dict) -> tuple:
    """根据探测结果给出一句话判断，返回 (控制台文本, 结果文件文本)。
    控制台用 ASCII 标记（Windows GBK 控制台无法打印 emoji）。"""
    if r["status"] == "FETCH_FAIL":
        return "[FAIL] 无法访问（网络/SSL/反爬拦截）", "❌ 无法访问（网络/SSL/反爬拦截）"
    if r["html_len"] < 5000:
        return "[WARN] 页面过小，疑似 JS 动态渲染", "⚠️ 页面过小，疑似 JS 动态渲染，列表爬不到"
    if not r["samples"]:
        return "[WARN] 无有效链接样本，疑似 JS 渲染", "⚠️ 无有效链接样本，疑似 JS 渲染或导航链接太少"
    return "[OK] 可用（见下方链接样本，可据此写 url_regex）", "✅ 可用（见下方链接样本，可据此写 url_regex）"


def main():
    only_new = '--all' not in sys.argv
    targets = CANDIDATES if only_new else [c for c in CANDIDATES if c['name'] not in
                                           ('中央国家机关招聘平台zpgg', '江苏省委组织部',
                                            '广东组织工作网', '中国公共招聘网', '国务院国资委')]
    lines = []
    for c in targets:
        print("=" * 72)
        lines.append("=" * 72)
        print(f"[{c['name']}] {c['url']}")
        lines.append(f"[{c['name']}] {c['url']}")
        try:
            r = probe(c['url'])
            judge_txt, judge_file = _judge(r)
            print(f"  {judge_txt}  status={r['status']} html_len={r['html_len']} total_a={r['total_a']}")
            lines.append(f"  {judge_file}  status={r['status']} html_len={r['html_len']} total_a={r['total_a']}")
            for s in r.get('samples', []):
                print(f"    - {s['text']}  ->  {s['href']}")
                lines.append(f"    - {s['text']}  ->  {s['href']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            lines.append(f"  ERROR: {e}")
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"\n[探测结果已写入] {RESULT_FILE}（用 Get-Content {RESULT_FILE} -Encoding UTF8 查看）")


if __name__ == '__main__':
    main()
