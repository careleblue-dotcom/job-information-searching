# 马院就业信息搜集 - 项目审查记录（2026-07-01）

## 已修复 ✓

### P0 - 必须立即修复
1. ~~**index.html 前端页面不存在**~~ → 用户表示前端不需要改，跳过
2. ~~**中央平台数据未合并到 all_jobs.json**~~ → 已修复：crawler_central_gov.py 和 run_crawler_full.py 现在同时调用 save_and_merge 写入 all_jobs.json

### P1 - 高优先级
3. ~~**crawler_central_gov.py 第 21 行 _NETLOC bug**~~ → 已修复：改为先 match 再取 group(2)，同时修复 DELAY 未导入的 NameError（改为 BASE_DELAY）
4. ~~**cleanup.py audit 函数变量遮蔽**~~ → 已修复：内层循环改为 data[i] 获取正确记录
5. ~~**CI 爬虫流程不完整**~~ → 已修复：crawler.yml 补充了 crawler_jszzb.py、crawler_gdzzb.py、crawler_sasac.py、crawler_university_marx.py

### P2 - 中优先级
6. ~~**deadline 字段几乎为空**~~ → 已修复：扩展了 parse_job_html 中的 deadline 正则（新增"报名时间为X至Y"、"报名截止时间X"、"截止时间X"等模式），parse_deadline 也支持范围格式取结束日期
7. ~~**source 字段约 26 条为"未知来源"**~~ → 已修复：批量脚本将 26 条全部修正为"中央国家机关招聘平台"，同时 crawler_central_gov.py 改用 SOURCE_NAME 常量传递正确来源
8. ~~**.gitignore 需排除运行时文件**~~ → 已修复：明确排除 seen_urls.json、failed_urls.json、备份文件、central_gov_jobs_full.json、logs/、.pytest_cache/、nul，同时显式保留 all_jobs.json 和 _meta.json

### P3 - 低优先级
9. **crawler_university_marx.py URL 硬编码易失效** → 未改（已有维护注释提示）
10. ~~**UNIVERSITY_SOURCES 中数据标注错误**~~ → 已修复：湖北理工学院（skb.hbpu.edu.cn）标注从"南京医科大学马克思主义学院"改为"湖北理工学院马克思主义学院"
11. ~~**requirements-dev.txt 与 requirements.txt 差异不明**~~ → 已修复：requirements.txt 添加注释说明开发/测试用 requirements-dev.txt

## 未修复（用户明确表示不改）
- index.html 前端页面不存在（用户表示前端不需要改）
- 自适应爬取间隔（用户表示不需要）

## 测试验证
- pytest 33 passed, 1 skipped（网络测试跳过）✓
