"""数据清理工具：审查 + 去重 + 修复"""
import json
import re
import shutil
import os
import unicodedata
from collections import Counter
from datetime import datetime
from config import PROVINCES, DEFAULT_SOURCE
from shared import extract_category, logger, _dedupe, _ensure_source

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
    _ensure_source(data)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已保存 {len(data)} 条到 {DATA_FILE}")


# ─── 审计（只读） ───────────────────────────────────

def _is_cjk(ch):
    """判断字符是否属于 CJK 统一汉字区间（0x4E00–0x9FFF）。"""
    return 0x4E00 <= ord(ch) <= 0x9FFF


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
        if len(c) <= 20:
            continue
        # 乱码判定：计算非"常见正常字符"占比。
        # 正常字符包括：CJK汉字、中文标点、ASCII可打印字符。
        # 注意：之前用 set('\u4e00-\u9fff') 是 bug（set 字面量不会展开为范围），
        # 这里改用区间判断函数。
        normal = 0
        for ch in c:
            if _is_cjk(ch) or ch.isascii() and ch.isprintable() or unicodedata.category(ch).startswith('P'):
                normal += 1
        ratio = 1 - normal / max(len(c), 1)
        if ratio > 0.2:
            mojibake.append((i, j.get('title', '')[:50], ratio))
    print('\n=== 可能乱码内容 ===')
    for i, t, r in mojibake:
        print(f'  [{i}] title={t} ratio={r:.2f}')

    remove_set = set(idx for idx, *_ in bad + [(s,) for s in short])
    print(f'\n建议删除索引(共{len(remove_set)}条): {sorted(remove_set)}')


# ─── 第一轮清理 ───────────────────────────────────

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

    # 地区修复：优先匹配 source，再匹配标题+正文
    for j in deduped:
        src = (j.get('source') or '')
        title = (j.get('title') or '')
        content = (j.get('content') or '')
        combined = src + ' ' + title + ' ' + content
        matched = False
        for name in PROVINCES:
            if name in src:
                j['region'] = name
                matched = True
                break
        if not matched:
            for name in PROVINCES:
                if name in combined:
                    j['region'] = name
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

    # 标题去重复用 shared._dedupe（URL + 标题归一化双重判断）
    deduped = _dedupe(data)
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
