"""数据清理工具：审查 + 去重 + 修复"""
import json
import re
import shutil
import os
from collections import Counter
from datetime import datetime
from shared import extract_category, logger

DATA_FILE = 'data/all_jobs.json'


def backup():
    backup_file = f'data/all_jobs_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    shutil.copy2(DATA_FILE, backup_file)
    print(f"[备份] 已备份到: {backup_file}")
    return backup_file


def load():
    with open(DATA_FILE, encoding='utf-8') as f:
        return json.load(f)


def save(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已保存 {len(data)} 条到 {DATA_FILE}")


# ─── 审计（只读） ───────────────────────────────────

def audit(data):
    print(f'总数据: {len(data)}条\n')

    bad = []
    for i, j in enumerate(data):
        t = (j.get('title') or '').strip()
        if len(t) <= 3 or t in ['学生', '首页', 'TOP', '...', '', ' ']:
            bad.append((i, t[:40], j.get('category'), j.get('source', '')[:30]))

    print('=== 异常标题 ===')
    for idx, t, cat, src in bad:
        print(f'  [{idx}] title="{t}" cat={cat} src={src}')

    short = []
    for i, j in enumerate(data):
        c = (j.get('content') or '')
        if len(c.strip()) < 20:
            short.append(i)

    print('\n=== 内容过短(<20字) ===')
    for i in short:
        print(f'  [{i}] title="{j.get("title","")[:40]}" content_len={len(c.strip())}')

    cats = Counter(j.get('category') or '未知' for j in data)
    print('\n=== 分类分布 ===')
    for k, v in cats.most_common():
        print(f'  {k}: {v}')

    regs = Counter(j.get('region') or '' for j in data)
    print('\n=== 地区分布 ===')
    for k, v in regs.most_common():
        print(f'  {k or "[空]"}: {v}')

    titles = [j.get('title') or '' for j in data]
    dupes = [(t, titles.count(t)) for t in set(titles) if titles.count(t) >= 3]
    print('\n=== 高重复标题(>=3次) ===')
    for t, c in sorted(dupes, key=lambda x: -x[1])[:15]:
        print(f'  ({c}x) {t[:70]}')

    mojibake = []
    for i, j in enumerate(data):
        c = (j.get('content') or '')
        common = set(
            '\t\n\r ，。、：；！？""''（）《》【】—…··0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.;:!?()[]-+/=%&@#$*^<>`~\u4e00-\u9fff\uff09\uff08\u3001\u300a\u300b')
        ratio = sum(1 for ch in c if ch not in common) / max(len(c), 1)
        if ratio > 0.2 and len(c) > 20:
            mojibake.append((i, j.get('title', '')[:50], ratio))
    print('\n=== 可能乱码内容 ===')
    for i, t, r in mojibake:
        print(f'  [{i}] title={t} ratio={r:.2f}')

    remove_set = set(idx for idx, *_ in bad + [(s,) for s in short])
    print(f'\n建议删除索引(共{len(remove_set)}条): {sorted(remove_set)}')


# ─── 第一轮清理 ───────────────────────────────────

PROVINCES = {
    '北京': '北京', '天津': '天津', '河北': '河北', '山西': '山西',
    '内蒙古': '内蒙古', '辽宁': '辽宁', '吉林': '吉林', '黑龙江': '黑龙江',
    '上海': '上海', '江苏': '江苏', '浙江': '浙江', '安徽': '安徽',
    '福建': '福建', '江西': '江西', '山东': '山东', '河南': '河南',
    '湖北': '湖北', '湖南': '湖南', '广东': '广东', '广西': '广西',
    '海南': '海南', '重庆': '重庆', '四川': '四川', '贵州': '贵州',
    '云南': '云南', '西藏': '西藏', '陕西': '陕西', '甘肃': '甘肃',
    '青海': '青海', '宁夏': '宁夏', '新疆': '新疆'
}


def round1(data):
    backup()
    print(f'原始数据: {len(data)} 条')

    remove_urls = set()
    for j in data:
        t = (j.get('title') or '').strip()
        c = (j.get('content') or '').strip()
        if len(t) <= 2 or t in ['首页', '学生', 'TOP', '--']:
            remove_urls.add(j.get('url', ''))
        elif len(c) < 20:
            remove_urls.add(j.get('url', ''))
        elif c in ['TOP...', '...', 'TOP', '教职工在校生...', '通知公告首页通知公告通知公告'] or c.startswith('教职工'):
            remove_urls.add(j.get('url', ''))

    seen = set()
    deduped = []
    for j in data:
        url = j.get('url', '')
        if url in seen or url in remove_urls:
            continue
        seen.add(url)
        deduped.append(j)

    print(f'去重后: {len(deduped)} 条 (删除 {len(data) - len(deduped)} 条)')

    for j in deduped:
        src = (j.get('source') or '')
        title = (j.get('title') or '')
        content = (j.get('content') or '')
        combined = src + ' ' + title + ' ' + content
        matched = False
        for name, val in PROVINCES.items():
            if name in src:
                j['region'] = val
                matched = True
                break
        if not matched:
            for name, val in PROVINCES.items():
                if name in combined:
                    j['region'] = val
                    matched = True
                    break
        if not matched:
            j['region'] = '全国'

    for j in deduped:
        j['category'] = extract_category(j.get('title', ''), j.get('content', ''))

    cats = Counter(j.get('category') for j in deduped)
    print('\n分类:')
    for k, v in cats.most_common():
        print(f'  {k}: {v}')

    save(deduped)
    return deduped


# ─── 第二轮清理 ───────────────────────────────────

def round2(data):
    backup()
    print(f'当前数据: {len(data)} 条')

    seen = set()
    deduped = []
    for j in data:
        t = (j.get('title') or '').strip()
        if t in seen:
            continue
        seen.add(t)
        deduped.append(j)
    print(f'标题去重后: {len(deduped)} 条 (删除 {len(data) - len(deduped)} 条)')

    final = []
    for j in deduped:
        t = (j.get('title') or '').strip()
        c = (j.get('content') or '').strip()
        if len(t) <= 2 or len(c) < 15:
            print(f'  删除: title="{t[:30]}" content_len={len(c)}')
            continue
        final.append(j)

    print(f'最终: {len(final)} 条')

    cats = Counter(j.get('category') for j in final)
    regs = Counter(j.get('region') for j in final)
    print('\n=== 最终分类 ===')
    for k, v in cats.most_common():
        print(f'  {k}: {v}')
    print('\n=== 最终地区 ===')
    for k, v in regs.most_common():
        print(f'  {k or "[空]"}: {v}')

    save(final)
    return final


# ─── 入口 ─────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='数据清理工具')
    parser.add_argument('mode', nargs='?', default='all',
                        choices=['audit', 'round1', 'round2', 'all'],
                        help='运行模式: audit(仅审查) / round1(去重+修复) / round2(标题去重) / all(全流程)')
    args = parser.parse_args()

    data = load()

    if args.mode == 'audit':
        audit(data)
    elif args.mode == 'round1':
        round1(load())
    elif args.mode == 'round2':
        round2(load())
    else:
        d = round1(load())
        round2(d)


if __name__ == '__main__':
    main()
