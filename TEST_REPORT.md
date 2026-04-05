# GitHub Recruiter 测试报告

## 测试环境

| 项目 | 值 |
|------|------|
| 测试时间 | 2026-04-03 22:41:13 |
| Python 版本 | 3.12.4 |
| 操作系统 | Darwin 23.5.0 |
| 项目目录 | `/Users/annesheartrecord/Desktop/github-recruiter` |
| 虚拟环境 | `.venv` |

## 测试结果汇总

| 指标 | 数量 |
|------|------|
| 总测试数 | 28 |
| ✅ 通过 | 27 |
| ❌ 失败 | 1 |
| 通过率 | 96.4% |

**各模块统计：**

| 模块 | 通过 | 失败 | 通过率 |
|------|------|------|--------|
| Config | 3 | 0 | 100% |
| DB | 7 | 0 | 100% |
| Email Finder | 8 | 0 | 100% |
| Mailer | 5 | 0 | 100% |
| CLI | 4 | 0 | 100% |
| 集成测试 | 0 | 1 | 0% |

## 详细结果

### 1. Config 模块

- ✅ **加载 config.example.yaml**
  - `sections=['github', 'smtp', 'search', 'sending']`
- ✅ **缺失配置文件报 FileNotFoundError**
  - `配置文件 /tmp/_nonexistent_config_12345.yaml 不存在，请从 config.example.yaml 复制并修改`
- ✅ **缺失字段使用默认值填充**
  - `token=test123, smtp.host=smtp.gmail.com`

### 2. DB 模块

- ✅ **自动建表 (candidates + send_log)**
  - `tables={'send_log', 'sqlite_sequence', 'candidates'}`
- ✅ **upsert_candidate 新增**
  - `username=testuser1`
- ✅ **upsert_candidate 更新去重（仓库+关键词合并）**
  - `repos=['repo/a', 'repo/c', 'repo/b'], keyword=golang,python`
- ✅ **get_candidates 按状态过滤**
  - `all=3, pending=2, sent=1`
- ✅ **get_today_send_count**
  - `before=0, after=1`
- ✅ **mark_sent 成功**
  - `candidate 1 → status=sent`
- ✅ **mark_sent 失败场景**
  - `status=failed, error=SMTP timeout`

### 3. Email Finder 模块

- ✅ **is_valid_email: 有效邮箱 ('user@example.com')**
  - `expected=True, got=True`
- ✅ **is_valid_email: 带+和.的有效邮箱 ('test.dev+tag@company.io')**
  - `expected=True, got=True`
- ✅ **is_valid_email: 子域名邮箱 ('valid@sub.domain.com')**
  - `expected=True, got=True`
- ✅ **is_valid_email: GitHub noreply ('user@users.noreply.github.com')**
  - `expected=False, got=False`
- ✅ **is_valid_email: 含 noreply 的邮箱 ('noreply@example.com')**
  - `expected=False, got=False`
- ✅ **is_valid_email: 空字符串 ('')**
  - `expected=False, got=False`
- ✅ **is_valid_email: None 值 (None)**
  - `expected=False, got=False`
- ✅ **is_valid_email: 无@符号 ('not-an-email')**
  - `expected=False, got=False`

### 4. Mailer 模块

- ✅ **load_template(default.txt)**
  - `subject='看到您在 {repos} 的贡献，想和您聊聊', body_len=181`
- ✅ **load_template 缺失文件报 FileNotFoundError**
- ✅ **render_template 变量替换**
  - `rendered='Hello Alice, you contributed to awesome-project!'`
- ✅ **render_template None值处理**
  - `rendered='Hi , from TestCo'`
- ✅ **render_template 未知变量保留原样**
  - `rendered='Hi Bob, your email is {email}'`

### 5. CLI 冒烟测试

- ✅ **github-recruiter --help**
  - `rc=0, output=Usage: github-recruiter [OPTIONS] COMMAND [ARGS]...    GitHub Recruiter - 从 GitHub 仓库中发现人才并自动触达  Options:   -c, --config TEXT  配置文件路径   --help`
- ✅ **github-recruiter search --help**
  - `rc=0, output=Usage: github-recruiter search [OPTIONS] KEYWORD    搜索关键词相关仓库并采集贡献者信息  Options:   -l, --language TEXT             限定编程语言，如 python/go/rust   -s, --min-`
- ✅ **github-recruiter list (空库)**
  - `rc=0, stdout=暂无候选人数据, stderr=`
- ✅ **github-recruiter stats (空库)**
  - `rc=0, stdout=📊 统计信息    总候选人: 0   有邮箱:   0   待发送:   0   已发送:   0   发送失败: 0   今日已发: 0`

### 6. 集成测试

- ❌ **search 无认证 (test --min-stars 10000 --max-repos 1)**
  - `rc=1, output=搜索关键词: test 最低 Stars: 10000  Traceback (most recent call last):   File "/Users/annesheartrecord/Desktop/github-recruiter/.venv/bin/github-recruiter", line 8, in <module>     sys.exit(cli())              ^^^^^   File "/Users/annesheartrecord/Desktop/github-recruiter/.venv/lib/python3.12/`

## 结论

共执行 **28** 项测试，**27** 项通过，**1** 项失败，通过率 **96.4%**。

以下测试未通过：

- **[集成测试]** search 无认证 (test --min-stars 10000 --max-repos 1)
