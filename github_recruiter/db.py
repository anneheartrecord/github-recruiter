import json
import sqlite3
import os
from datetime import datetime, date


DB_PATH = "recruiter.db"


def get_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """获取数据库连接，自动建表"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            email TEXT,
            bio TEXT,
            company TEXT,
            blog TEXT,
            repos TEXT DEFAULT '[]',
            keyword TEXT,
            status TEXT DEFAULT 'pending',
            found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS send_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            email TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 1,
            error TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )
    """)
    conn.commit()
    return conn


def upsert_candidate(conn: sqlite3.Connection, username: str, name: str,
                      email: str, bio: str, company: str, blog: str,
                      repos: list, keyword: str) -> bool:
    """插入或更新候选人。返回 True 表示新插入，False 表示已存在（更新）"""
    existing = conn.execute(
        "SELECT id, repos, keyword FROM candidates WHERE username = ?",
        (username,)
    ).fetchone()

    if existing:
        # 合并仓库列表和关键词
        old_repos = json.loads(existing["repos"] or "[]")
        merged_repos = list(set(old_repos + repos))
        old_keywords = set(existing["keyword"].split(",")) if existing["keyword"] else set()
        old_keywords.add(keyword)

        conn.execute("""
            UPDATE candidates
            SET name = COALESCE(?, name),
                email = COALESCE(?, email),
                bio = COALESCE(?, bio),
                company = COALESCE(?, company),
                blog = COALESCE(?, blog),
                repos = ?,
                keyword = ?
            WHERE username = ?
        """, (name, email, bio, company, blog,
              json.dumps(merged_repos), ",".join(old_keywords), username))
        conn.commit()
        return False
    else:
        conn.execute("""
            INSERT INTO candidates (username, name, email, bio, company, blog, repos, keyword)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, name, email, bio, company, blog, json.dumps(repos), keyword))
        conn.commit()
        return True


def get_candidates(conn: sqlite3.Connection, status: str = None) -> list:
    """获取候选人列表"""
    if status:
        rows = conn.execute(
            "SELECT * FROM candidates WHERE status = ? ORDER BY found_at DESC",
            (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM candidates ORDER BY found_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_today_send_count(conn: sqlite3.Connection) -> int:
    """获取今天已发送的邮件数"""
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM send_log WHERE date(sent_at) = ? AND success = 1",
        (today,)
    ).fetchone()
    return row["cnt"]


def mark_sent(conn: sqlite3.Connection, candidate_id: int, email: str,
              success: bool = True, error: str = None):
    """记录发送结果"""
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO send_log (candidate_id, email, sent_at, success, error) VALUES (?, ?, ?, ?, ?)",
        (candidate_id, email, now, int(success), error)
    )
    new_status = "sent" if success else "failed"
    conn.execute(
        "UPDATE candidates SET status = ?, sent_at = ? WHERE id = ?",
        (new_status, now if success else None, candidate_id)
    )
    conn.commit()
