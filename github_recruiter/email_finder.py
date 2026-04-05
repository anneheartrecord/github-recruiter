import re
from rich.console import Console

from .github_api import GitHubAPI

console = Console()

# 需要过滤的邮箱模式
NOREPLY_PATTERNS = [
    r".*@users\.noreply\.github\.com$",
    r".*noreply.*",
]

# 从文本中提取邮箱的正则
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def is_valid_email(email: str) -> bool:
    """检查邮箱是否有效（排除 noreply 等无效邮箱）"""
    if not email or "@" not in email:
        return False
    email_lower = email.lower().strip()
    for pattern in NOREPLY_PATTERNS:
        if re.match(pattern, email_lower):
            return False
    return bool(EMAIL_REGEX.match(email_lower))


def find_email(api: GitHubAPI, username: str) -> str | None:
    """
    尝试多种方式获取用户邮箱，按优先级返回第一个有效邮箱

    优先级:
    1. GitHub API 用户信息中的 email 字段
    2. 公开事件（PushEvent）中的 commit email
    3. 用户 bio / blog 中的邮箱
    """
    # 1. 用户信息中直接获取
    user_info = api.get_user_info(username)
    if user_info["email"] and is_valid_email(user_info["email"]):
        return user_info["email"]

    # 2. 从 PushEvent 中提取
    event_emails = api.get_user_events_emails(username)
    for email in event_emails:
        if is_valid_email(email):
            return email

    # 3. 从 bio 中提取
    bio = user_info.get("bio", "") or ""
    blog = user_info.get("blog", "") or ""
    text = f"{bio} {blog}"
    found = EMAIL_REGEX.findall(text)
    for email in found:
        if is_valid_email(email):
            return email

    return None


def find_email_with_info(api: GitHubAPI, username: str) -> dict:
    """获取用户信息并查找邮箱，返回完整的候选人信息"""
    user_info = api.get_user_info(username)
    email = None

    # 1. API 直接获取
    if user_info["email"] and is_valid_email(user_info["email"]):
        email = user_info["email"]

    # 2. PushEvent
    if not email:
        event_emails = api.get_user_events_emails(username)
        for e in event_emails:
            if is_valid_email(e):
                email = e
                break

    # 3. bio/blog 正则
    if not email:
        bio = user_info.get("bio", "") or ""
        blog = user_info.get("blog", "") or ""
        found = EMAIL_REGEX.findall(f"{bio} {blog}")
        for e in found:
            if is_valid_email(e):
                email = e
                break

    return {
        "username": user_info["username"],
        "name": user_info["name"],
        "email": email,
        "bio": user_info["bio"],
        "company": user_info["company"],
        "blog": user_info["blog"],
    }
