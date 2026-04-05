#!/usr/bin/env python3
"""GitHub Recruiter 全模块测试脚本"""

import os
import sys
import json
import shutil
import sqlite3
import subprocess
import traceback
from datetime import datetime, date

# 切换到项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

results = []  # [(模块, 测试名, 通过?, 详情)]


def record(module, name, passed, detail=""):
    results.append((module, name, passed, detail))
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} | {module} | {name}")
    if detail and not passed:
        print(f"         {detail[:200]}")


# ============================================================
# 1. Config 模块
# ============================================================
print("\n=== 1. Config 模块 ===")

from github_recruiter.config import load_config, DEFAULT_CONFIG

# 1.1 加载 config.example.yaml (先复制为临时文件)
try:
    tmp_config = os.path.join(PROJECT_DIR, "_test_config.yaml")
    shutil.copy("config.example.yaml", tmp_config)
    cfg = load_config(tmp_config)
    has_all_keys = set(cfg.keys()) == set(DEFAULT_CONFIG.keys())
    assert has_all_keys, f"keys mismatch: {cfg.keys()}"
    assert cfg["smtp"]["port"] == 587
    assert cfg["search"]["min_stars"] == 100
    record("Config", "加载 config.example.yaml", True, f"sections={list(cfg.keys())}")
except Exception as e:
    record("Config", "加载 config.example.yaml", False, traceback.format_exc())
finally:
    if os.path.exists(tmp_config):
        os.remove(tmp_config)

# 1.2 缺失配置文件时报 FileNotFoundError
try:
    load_config("/tmp/_nonexistent_config_12345.yaml")
    record("Config", "缺失配置文件报 FileNotFoundError", False, "未抛出异常")
except FileNotFoundError as e:
    record("Config", "缺失配置文件报 FileNotFoundError", True, str(e))
except Exception as e:
    record("Config", "缺失配置文件报 FileNotFoundError", False, f"异常类型错误: {type(e).__name__}: {e}")

# 1.3 默认值填充
try:
    minimal = os.path.join(PROJECT_DIR, "_test_minimal.yaml")
    with open(minimal, "w") as f:
        f.write("github:\n  token: test123\n")
    cfg = load_config(minimal)
    assert cfg["github"]["token"] == "test123"
    assert cfg["smtp"]["host"] == "smtp.gmail.com"
    assert cfg["sending"]["daily_limit"] == 50
    record("Config", "缺失字段使用默认值填充", True,
           f"token={cfg['github']['token']}, smtp.host={cfg['smtp']['host']}")
except Exception as e:
    record("Config", "缺失字段使用默认值填充", False, traceback.format_exc())
finally:
    if os.path.exists(minimal):
        os.remove(minimal)


# ============================================================
# 2. DB 模块
# ============================================================
print("\n=== 2. DB 模块 ===")

from github_recruiter.db import get_db, upsert_candidate, get_candidates, get_today_send_count, mark_sent

tmp_db = os.path.join(PROJECT_DIR, "_test.db")
if os.path.exists(tmp_db):
    os.remove(tmp_db)

# 2.1 自动建表
try:
    conn = get_db(tmp_db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {t["name"] for t in tables}
    assert "candidates" in table_names and "send_log" in table_names
    record("DB", "自动建表 (candidates + send_log)", True, f"tables={table_names}")
except Exception as e:
    record("DB", "自动建表 (candidates + send_log)", False, traceback.format_exc())

# 2.2 upsert_candidate - 新增
try:
    is_new = upsert_candidate(
        conn, username="testuser1", name="Test User",
        email="test@example.com", bio="Hello", company="TestCo",
        blog="https://test.com", repos=["repo/a", "repo/b"], keyword="python"
    )
    assert is_new is True, f"期望 True（新增），得到 {is_new}"
    row = conn.execute("SELECT * FROM candidates WHERE username='testuser1'").fetchone()
    assert row is not None and row["email"] == "test@example.com"
    record("DB", "upsert_candidate 新增", True, f"username={row['username']}")
except Exception as e:
    record("DB", "upsert_candidate 新增", False, traceback.format_exc())

# 2.3 upsert_candidate - 更新去重
try:
    is_new2 = upsert_candidate(
        conn, username="testuser1", name="Test User Updated",
        email="new@example.com", bio="Updated", company="NewCo",
        blog="https://new.com", repos=["repo/c"], keyword="golang"
    )
    assert is_new2 is False, f"期望 False（更新），得到 {is_new2}"
    row = conn.execute("SELECT * FROM candidates WHERE username='testuser1'").fetchone()
    repos = json.loads(row["repos"])
    assert "repo/c" in repos and "repo/a" in repos
    assert "python" in row["keyword"] and "golang" in row["keyword"]
    record("DB", "upsert_candidate 更新去重（仓库+关键词合并）", True,
           f"repos={repos}, keyword={row['keyword']}")
except Exception as e:
    record("DB", "upsert_candidate 更新去重（仓库+关键词合并）", False, traceback.format_exc())

# 2.4 get_candidates 按状态过滤
try:
    upsert_candidate(conn, "user_sent", "Sent", "sent@x.com", "", "", "", ["r/1"], "k1")
    conn.execute("UPDATE candidates SET status='sent' WHERE username='user_sent'")
    conn.commit()
    upsert_candidate(conn, "user_pending", "Pending", "p@x.com", "", "", "", ["r/2"], "k2")

    all_c = get_candidates(conn)
    pending_c = get_candidates(conn, status="pending")
    sent_c = get_candidates(conn, status="sent")

    assert len(all_c) >= 3
    assert all(c["status"] == "pending" for c in pending_c)
    assert all(c["status"] == "sent" for c in sent_c) and len(sent_c) >= 1
    record("DB", "get_candidates 按状态过滤", True,
           f"all={len(all_c)}, pending={len(pending_c)}, sent={len(sent_c)}")
except Exception as e:
    record("DB", "get_candidates 按状态过滤", False, traceback.format_exc())

# 2.5 get_today_send_count
try:
    count_before = get_today_send_count(conn)
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO send_log (candidate_id, email, sent_at, success) VALUES (1, 'a@b.com', ?, 1)",
        (now,)
    )
    conn.commit()
    count_after = get_today_send_count(conn)
    assert count_after == count_before + 1
    record("DB", "get_today_send_count", True, f"before={count_before}, after={count_after}")
except Exception as e:
    record("DB", "get_today_send_count", False, traceback.format_exc())

# 2.6 mark_sent
try:
    row = conn.execute("SELECT id FROM candidates WHERE status='pending' LIMIT 1").fetchone()
    cid = row["id"]
    mark_sent(conn, cid, "test@mark.com", success=True)
    updated = conn.execute("SELECT status, sent_at FROM candidates WHERE id=?", (cid,)).fetchone()
    assert updated["status"] == "sent"
    assert updated["sent_at"] is not None
    log = conn.execute("SELECT * FROM send_log WHERE candidate_id=? ORDER BY id DESC LIMIT 1", (cid,)).fetchone()
    assert log["success"] == 1
    record("DB", "mark_sent 成功", True, f"candidate {cid} → status={updated['status']}")
except Exception as e:
    record("DB", "mark_sent 成功", False, traceback.format_exc())

# 2.7 mark_sent 失败场景
try:
    upsert_candidate(conn, "failuser", "Fail", "fail@example.com", "", "", "", [], "test")
    fail_row = conn.execute("SELECT * FROM candidates WHERE username='failuser'").fetchone()
    mark_sent(conn, fail_row["id"], "fail@example.com", success=False, error="SMTP timeout")
    updated = conn.execute("SELECT * FROM candidates WHERE id=?", (fail_row["id"],)).fetchone()
    log = conn.execute("SELECT * FROM send_log WHERE candidate_id=? ORDER BY id DESC LIMIT 1", (fail_row["id"],)).fetchone()
    assert updated["status"] == "failed"
    assert log["error"] == "SMTP timeout"
    record("DB", "mark_sent 失败场景", True, f"status={updated['status']}, error={log['error']}")
except Exception as e:
    record("DB", "mark_sent 失败场景", False, traceback.format_exc())

conn.close()
if os.path.exists(tmp_db):
    os.remove(tmp_db)


# ============================================================
# 3. Email Finder 模块
# ============================================================
print("\n=== 3. Email Finder 模块 ===")

from github_recruiter.email_finder import is_valid_email

test_cases = [
    ("有效邮箱", "user@example.com", True),
    ("带+和.的有效邮箱", "test.dev+tag@company.io", True),
    ("子域名邮箱", "valid@sub.domain.com", True),
    ("GitHub noreply", "user@users.noreply.github.com", False),
    ("含 noreply 的邮箱", "noreply@example.com", False),
    ("空字符串", "", False),
    ("None 值", None, False),
    ("无@符号", "not-an-email", False),
]

for name, email, expected in test_cases:
    try:
        result = is_valid_email(email)
        record("Email Finder", f"is_valid_email: {name} ({email!r})", result == expected,
               f"expected={expected}, got={result}")
    except Exception as e:
        record("Email Finder", f"is_valid_email: {name} ({email!r})", False, str(e))


# ============================================================
# 4. Mailer 模块
# ============================================================
print("\n=== 4. Mailer 模块 ===")

from github_recruiter.mailer import load_template, render_template

# 4.1 load_template
try:
    tpl_path = os.path.join(PROJECT_DIR, "templates", "default.txt")
    subject, body = load_template(tpl_path)
    assert subject, "Subject 不应为空"
    assert "{repos}" in subject or "{name}" in body
    assert len(body) > 0
    record("Mailer", "load_template(default.txt)", True,
           f"subject='{subject[:60]}', body_len={len(body)}")
except Exception as e:
    record("Mailer", "load_template(default.txt)", False, traceback.format_exc())

# 4.2 load_template 缺失文件
try:
    load_template("/tmp/_nonexistent_template.txt")
    record("Mailer", "load_template 缺失文件报 FileNotFoundError", False, "未抛出异常")
except FileNotFoundError:
    record("Mailer", "load_template 缺失文件报 FileNotFoundError", True)
except Exception as e:
    record("Mailer", "load_template 缺失文件报 FileNotFoundError", False, f"{type(e).__name__}: {e}")

# 4.3 render_template 变量替换
try:
    tpl = "Hello {name}, you contributed to {repos}!"
    rendered = render_template(tpl, {"name": "Alice", "repos": "awesome-project"})
    assert rendered == "Hello Alice, you contributed to awesome-project!"
    record("Mailer", "render_template 变量替换", True, f"rendered='{rendered}'")
except Exception as e:
    record("Mailer", "render_template 变量替换", False, traceback.format_exc())

# 4.4 render_template None 值处理
try:
    tpl = "Hi {name}, from {company}"
    rendered = render_template(tpl, {"name": None, "company": "TestCo"})
    assert "{name}" not in rendered, f"None 值未被替换: {rendered}"
    assert "TestCo" in rendered
    record("Mailer", "render_template None值处理", True, f"rendered='{rendered}'")
except Exception as e:
    record("Mailer", "render_template None值处理", False, traceback.format_exc())

# 4.5 render_template 未替换的变量保留原样
try:
    tpl = "Hi {name}, your email is {email}"
    rendered = render_template(tpl, {"name": "Bob"})
    assert rendered == "Hi Bob, your email is {email}"
    record("Mailer", "render_template 未知变量保留原样", True, f"rendered='{rendered}'")
except Exception as e:
    record("Mailer", "render_template 未知变量保留原样", False, traceback.format_exc())


# ============================================================
# 5. CLI 冒烟测试
# ============================================================
print("\n=== 5. CLI 冒烟测试 ===")

VENV_BIN = os.path.join(PROJECT_DIR, ".venv", "bin")
CLI_ENV = {**os.environ, "PATH": VENV_BIN + ":" + os.environ.get("PATH", "")}

def run_cli(args_str, timeout=15):
    return subprocess.run(
        args_str.split(), capture_output=True, text=True,
        timeout=timeout, cwd=PROJECT_DIR, env=CLI_ENV
    )

# 为 list/stats 准备 config.yaml
shutil.copy("config.example.yaml", os.path.join(PROJECT_DIR, "config.yaml"))

# 5.1 --help
try:
    r = run_cli("github-recruiter --help")
    ok = r.returncode == 0 and "GitHub Recruiter" in r.stdout
    record("CLI", "github-recruiter --help", ok,
           f"rc={r.returncode}, output={r.stdout[:150].strip()}")
except Exception as e:
    record("CLI", "github-recruiter --help", False, str(e))

# 5.2 search --help
try:
    r = run_cli("github-recruiter search --help")
    ok = r.returncode == 0 and ("keyword" in r.stdout.lower() or "搜索" in r.stdout)
    record("CLI", "github-recruiter search --help", ok,
           f"rc={r.returncode}, output={r.stdout[:150].strip()}")
except Exception as e:
    record("CLI", "github-recruiter search --help", False, str(e))

# 5.3 list（空数据库）
try:
    # 确保没有旧的 recruiter.db
    db_file = os.path.join(PROJECT_DIR, "recruiter.db")
    if os.path.exists(db_file):
        os.remove(db_file)
    r = run_cli("github-recruiter list")
    record("CLI", "github-recruiter list (空库)", r.returncode == 0,
           f"rc={r.returncode}, stdout={r.stdout[:150].strip()}, stderr={r.stderr[:100].strip()}")
except Exception as e:
    record("CLI", "github-recruiter list (空库)", False, str(e))

# 5.4 stats（空数据库）
try:
    if os.path.exists(db_file):
        os.remove(db_file)
    r = run_cli("github-recruiter stats")
    ok = r.returncode == 0 and "0" in r.stdout
    record("CLI", "github-recruiter stats (空库)", ok,
           f"rc={r.returncode}, stdout={r.stdout[:200].strip()}")
except Exception as e:
    record("CLI", "github-recruiter stats (空库)", False, str(e))

# 清理 CLI 测试产物
for f in ["config.yaml", "recruiter.db"]:
    p = os.path.join(PROJECT_DIR, f)
    if os.path.exists(p):
        os.remove(p)


# ============================================================
# 6. 集成测试（无认证 GitHub search）
# ============================================================
print("\n=== 6. 集成测试 ===")

try:
    shutil.copy("config.example.yaml", os.path.join(PROJECT_DIR, "config.yaml"))
    r = subprocess.run(
        "github-recruiter search test --min-stars 10000 --max-repos 1".split(),
        capture_output=True, text=True, timeout=60,
        cwd=PROJECT_DIR, env=CLI_ENV
    )
    output = r.stdout + r.stderr
    if r.returncode == 0:
        record("集成测试", "search 无认证 (test --min-stars 10000 --max-repos 1)", True,
               f"rc=0, output={output[:300].strip()}")
    else:
        record("集成测试", "search 无认证 (test --min-stars 10000 --max-repos 1)", False,
               f"rc={r.returncode}, output={output[:300].strip()}")
except subprocess.TimeoutExpired:
    record("集成测试", "search 无认证", False, "超时 (60s)")
except Exception as e:
    record("集成测试", "search 无认证", False, str(e))
finally:
    for f in ["config.yaml", "recruiter.db"]:
        p = os.path.join(PROJECT_DIR, f)
        if os.path.exists(p):
            os.remove(p)


# ============================================================
# 生成 TEST_REPORT.md
# ============================================================
print("\n=== 生成测试报告 ===")

total = len(results)
passed = sum(1 for r in results if r[2])
failed = total - passed

# 按模块分组
from collections import OrderedDict
modules = OrderedDict()
for module, name, ok, detail in results:
    modules.setdefault(module, []).append((name, ok, detail))

module_keys = ["Config", "DB", "Email Finder", "Mailer", "CLI", "集成测试"]
section_titles = {
    "Config": "### 1. Config 模块",
    "DB": "### 2. DB 模块",
    "Email Finder": "### 3. Email Finder 模块",
    "Mailer": "### 4. Mailer 模块",
    "CLI": "### 5. CLI 冒烟测试",
    "集成测试": "### 6. 集成测试",
}

report = f"""# GitHub Recruiter 测试报告

## 测试环境

| 项目 | 值 |
|------|------|
| 测试时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| Python 版本 | {sys.version.split()[0]} |
| 操作系统 | {os.uname().sysname} {os.uname().release} |
| 项目目录 | `{PROJECT_DIR}` |
| 虚拟环境 | `.venv` |

## 测试结果汇总

| 指标 | 数量 |
|------|------|
| 总测试数 | {total} |
| ✅ 通过 | {passed} |
| ❌ 失败 | {failed} |
| 通过率 | {passed/total*100:.1f}% |

**各模块统计：**

| 模块 | 通过 | 失败 | 通过率 |
|------|------|------|--------|
"""

for mod in module_keys:
    if mod in modules:
        items = modules[mod]
        p = sum(1 for _, ok, _ in items if ok)
        f = len(items) - p
        rate = f"{p/len(items)*100:.0f}%"
        report += f"| {mod} | {p} | {f} | {rate} |\n"

report += "\n## 详细结果\n"

for mod in module_keys:
    if mod not in modules:
        continue
    report += f"\n{section_titles[mod]}\n\n"
    for name, ok, detail in modules[mod]:
        mark = "✅" if ok else "❌"
        report += f"- {mark} **{name}**\n"
        if detail:
            safe = detail.replace("\n", " ").replace("|", "\\|")[:300]
            report += f"  - `{safe}`\n"

report += f"""
## 结论

共执行 **{total}** 项测试，**{passed}** 项通过，**{failed}** 项失败，通过率 **{passed/total*100:.1f}%**。

"""

if failed == 0:
    report += "所有测试均通过，各模块功能正常。\n"
else:
    report += "以下测试未通过：\n\n"
    for mod, name, ok, detail in results:
        if not ok:
            report += f"- **[{mod}]** {name}\n"

report_path = os.path.join(PROJECT_DIR, "TEST_REPORT.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report)

print(f"\n报告已写入: {report_path}")
print(f"结果: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
