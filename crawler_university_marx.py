#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高校马克思主义学院招聘信息爬虫
从各高校官网和招聘平台抓取思政教师/辅导员招聘信息
适用于马克思主义理论、思政、政治学、哲学等相关专业
"""

from bs4 import BeautifulSoup
import time
import re
from config import HEADERS, DELAY
from shared import fetch_page, parse_date, save_and_merge, crawl_job_detail, logger

# 高校招聘信息来源配置
UNIVERSITY_SOURCES = [
    {
        'name': '山东大学人才招聘',
        'url': 'https://www.rsrczp.sdu.edu.cn/info/1043/6595.htm',
        'category': '高校招聘',
    },
    {
        'name': '南京大学人才招聘',
        'url': 'https://rczp.nju.edu.cn/zrjs/zrjsgwlb/20260317/i369629.html',
        'category': '高校招聘',
    },
    {
        'name': '大连理工大学马克思主义学院',
        'url': 'https://marx.dlut.edu.cn/info/1060/23722.htm',
        'category': '高校招聘',
    },
    {
        'name': '南京医科大学马克思主义学院',
        'url': 'https://skb.hbpu.edu.cn/info/1043/3200.htm',
        'category': '高校招聘',
    },
]

# 高校就业信息网列表（选调生/公务员公告发布平台）
UNIVERSITY_CAREER_SOURCES = [
    {
        'name': '北京大学就业指导中心',
        'url': 'https://scc.pku.edu.cn/home',
        'category': '选调生/公务员',
    },
    {
        'name': '清华大学就业指导中心',
        'url': 'https://career.tsinghua.edu.cn',
        'category': '选调生/公务员',
    },
]


def crawl_single_university(source):
    """爬取单个高校招聘信息"""
    logger.info('爬取高校招聘: %s - %s', source['name'], source['url'])

    job_data = crawl_job_detail(source['url'], source['name'])
    if job_data:
        job_data['category'] = source['category']
        return job_data
    return None


def crawl_gaoxiaojob_list():
    """
    爬取高校人才网马克思主义学院招聘列表
    注意：高校人才网可能有反爬，这里采用备用策略直接访问已知的高校招聘页面
    """
    logger.info('开始爬取高校马克思主义学院招聘信息')

    jobs = []

    # 已知的高校马克思主义学院/思政教师招聘公告
    known_pages = [
        {
            'title': '山东大学2026年思政课教师招聘公告',
            'url': 'https://www.rsrczp.sdu.edu.cn/info/1043/6595.htm',
            'source': '山东大学人才招聘网',
        },
        {
            'title': '南京大学马克思主义学院2026年度准聘长聘岗位（事业编制）招聘公告',
            'url': 'https://rczp.nju.edu.cn/zrjs/zrjsgwlb/20260317/i369629.html',
            'source': '南京大学人才招聘网',
        },
        {
            'title': '大连理工大学马克思主义学院2026年诚聘海内外优秀人才',
            'url': 'https://marx.dlut.edu.cn/info/1060/23722.htm',
            'source': '大连理工大学马克思主义学院',
        },
        {
            'title': '安徽工业大学马克思主义学院2026年招聘高层次人才公告',
            'url': 'https://www.gaoxiaojob.com/announcement/detail/371764.html',
            'source': '高校人才网',
        },
        {
            'title': '潍坊学院马克思主义学院2026年招聘启事',
            'url': 'https://mks.wfu.edu.cn/2026/0421/c3333a263894/page.htm',
            'source': '潍坊学院马克思主义学院',
        },
    ]

    for item in known_pages:
        logger.info('处理: %s', item['title'][:50])
        job_data = crawl_job_detail(item['url'], item['source'])
        if job_data:
            job_data['category'] = '高校招聘'
            jobs.append(job_data)
        else:
            # 保存基础信息
            jobs.append({
                'title': item['title'],
                'url': item['url'],
                'publish_date': '',
                'category': '高校招聘',
                'source': item['source'],
                'region': '全国',
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            })
        time.sleep(DELAY)

    return jobs


def crawl_nju_marx():
    """爬取南京大学马克思主义学院招聘公告（独立爬取，因为页面结构特殊）"""
    logger.info('爬取南京大学马克思主义学院招聘')
    url = 'https://rczp.nju.edu.cn/zrjs/zrjsgwlb/20260317/i369629.html'
    job_data = crawl_job_detail(url, '南京大学人才招聘网')
    if job_data:
        job_data['category'] = '高校招聘'
        return job_data
    return None


def crawl_institute_marx():
    """爬取中国社会科学院等研究机构招聘"""
    logger.info('开始爬取研究机构招聘信息')

    jobs = []

    # 中国社会科学院招聘（马克思主义理论相关）
    cass_pages = [
        {
            'title': '中国社会科学院2026年度公开招聘管理人员公告',
            'url': 'http://cass.cn/tongzhigonggao/202512/t20251211_5955191.shtml',
            'source': '中国社会科学院',
        },
        {
            'title': '中国社会科学院2026年度公开招聘第一批专业技术人员公告',
            'url': 'https://www.cssn.cn/ggzp/202512/t20251211_5955189.shtml',
            'source': '中国社会科学院',
        },
        {
            'title': '中国社会科学院2026年度公开招聘第二批专业技术人员公告',
            'url': 'http://naes.org.cn/cj_zwz/hd/gg/202605/t20260529_5998341.shtml',
            'source': '中国社会科学院',
        },
    ]

    for item in cass_pages:
        logger.info('处理: %s', item['title'][:50])
        job_data = crawl_job_detail(item['url'], item['source'])
        if job_data:
            job_data['category'] = '事业单位'
            jobs.append(job_data)
        else:
            jobs.append({
                'title': item['title'],
                'url': item['url'],
                'publish_date': '',
                'category': '事业单位',
                'source': item['source'],
                'region': '全国',
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            })
        time.sleep(DELAY)

    return jobs


def main():
    print("=" * 60)
    print("高校马克思主义学院/研究机构招聘信息爬虫")
    print("=" * 60)

    all_jobs = []

    # 1. 高校马克思主义学院招聘
    print("\n--- 爬取高校马克思主义学院招聘 ---")
    uni_jobs = crawl_gaoxiaojob_list()
    all_jobs.extend(uni_jobs)
    print(f"  高校招聘: {len(uni_jobs)} 条")

    time.sleep(DELAY * 2)

    # 2. 研究机构招聘（社科院等）
    print("\n--- 爬取研究机构招聘 ---")
    inst_jobs = crawl_institute_marx()
    all_jobs.extend(inst_jobs)
    print(f"  研究机构: {len(inst_jobs)} 条")

    if all_jobs:
        save_and_merge(all_jobs)
        print(f"\n爬取完成！")
        print(f"  合计: {len(all_jobs)} 条")
    else:
        print("\n[警告] 未获取到数据")


if __name__ == '__main__':
    main()
