import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from rich.console import Console

from .db import get_today_send_count, mark_sent

console = Console()


def load_template(template_path: str) -> tuple[str, str]:
    """
    加载邮件模板，返回 (subject, body)
    模板第一行为 Subject: xxx，其余为正文
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"邮件模板不存在: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.strip().split("\n")
    subject = ""
    body_start = 0

    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()
    return subject, body


def render_template(text: str, variables: dict) -> str:
    """渲染模板变量"""
    result = text
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value) if value else "")
    return result


def send_email(smtp_config: dict, to_email: str, subject: str, body: str,
               dry_run: bool = False) -> tuple[bool, str | None]:
    """
    发送邮件
    返回 (success, error_msg)
    """
    if dry_run:
        console.print(f"  [dim][DRY RUN] 发送到: {to_email}[/dim]")
        console.print(f"  [dim]Subject: {subject}[/dim]")
        console.print(f"  [dim]Body: {body[:100]}...[/dim]")
        return True, None

    try:
        msg = MIMEMultipart()
        msg["From"] = f"{smtp_config['from_name']} <{smtp_config['username']}>"
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
            server.starttls()
            server.login(smtp_config["username"], smtp_config["password"])
            server.send_message(msg)

        return True, None

    except Exception as e:
        return False, str(e)


def send_to_candidates(conn, candidates: list, smtp_config: dict,
                       sending_config: dict, dry_run: bool = False) -> dict:
    """
    批量发送邮件给候选人列表
    返回统计信息 {sent: int, failed: int, skipped: int}
    """
    template_path = sending_config.get("template", "templates/default.txt")
    delay = sending_config.get("delay_seconds", 10)
    daily_limit = sending_config.get("daily_limit", 50)

    subject_tpl, body_tpl = load_template(template_path)
    stats = {"sent": 0, "failed": 0, "skipped": 0}

    for candidate in candidates:
        # 检查每日限额
        if not dry_run:
            today_count = get_today_send_count(conn)
            if today_count >= daily_limit:
                console.print(f"[yellow]已达今日发送上限 ({daily_limit})，停止发送[/yellow]")
                break

        email = candidate.get("email")
        if not email:
            stats["skipped"] += 1
            continue

        # 渲染模板
        import json
        repos_list = json.loads(candidate.get("repos", "[]"))
        repos_str = ", ".join(repos_list[:3]) if repos_list else "开源项目"

        variables = {
            "name": candidate.get("name") or candidate.get("username", ""),
            "username": candidate.get("username", ""),
            "repos": repos_str,
            "keyword": candidate.get("keyword", ""),
            "from_name": smtp_config.get("from_name", ""),
            "email": email,
            "bio": candidate.get("bio", ""),
            "company": candidate.get("company", ""),
        }

        subject = render_template(subject_tpl, variables)
        body = render_template(body_tpl, variables)

        console.print(f"  发送到 [cyan]{candidate['username']}[/cyan] <{email}>...")
        success, error = send_email(smtp_config, email, subject, body, dry_run=dry_run)

        if not dry_run:
            mark_sent(conn, candidate["id"], email, success=success, error=error)

        if success:
            stats["sent"] += 1
        else:
            stats["failed"] += 1
            console.print(f"  [red]失败: {error}[/red]")

        # 发送间隔
        if not dry_run and delay > 0:
            time.sleep(delay)

    return stats
