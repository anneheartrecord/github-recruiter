import time
import random
import requests
from rich.console import Console

console = Console()

API_BASE = "https://api.github.com"

# 可重试的异常和状态码
_RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
_MAX_RETRIES = 5
_BASE_DELAY = 1.5  # 每次请求间隔基础秒数


class GitHubAPI:
    """GitHub API 封装，处理认证和限速"""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "github-recruiter/1.0 (https://github.com/github-recruiter)",
        })
        if token:
            self.session.headers["Authorization"] = f"token {token}"
        self._last_request_time = 0.0

    def _wait_between_requests(self):
        """在请求之间添加延迟，避免触发连接限制"""
        elapsed = time.time() - self._last_request_time
        delay = _BASE_DELAY + random.uniform(0, 0.5)
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def _check_rate_limit(self, resp: requests.Response):
        """主动检查 rate limit 头，剩余为 0 时提前等待"""
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_time - int(time.time()), 1)
            console.print(f"[yellow]Rate limit 即将耗尽，等待 {wait} 秒...[/yellow]")
            time.sleep(wait + 1)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """发送请求，自动处理 rate limit 和重试"""
        kwargs.setdefault("timeout", 30)

        for attempt in range(_MAX_RETRIES):
            self._wait_between_requests()
            try:
                resp = self.session.request(method, url, **kwargs)
                self._last_request_time = time.time()
            except _RETRYABLE_EXCEPTIONS as e:
                backoff = (2 ** attempt) + random.uniform(0, 1)
                console.print(
                    f"[yellow]请求失败 ({type(e).__name__})，"
                    f"{backoff:.1f}s 后重试 ({attempt+1}/{_MAX_RETRIES})[/yellow]"
                )
                time.sleep(backoff)
                continue

            # 处理 403 rate limit
            if resp.status_code == 403:
                remaining = int(resp.headers.get("X-RateLimit-Remaining", -1))
                if remaining == 0:
                    reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
                    wait = max(reset_time - int(time.time()), 1)
                    console.print(f"[yellow]Rate limit，等待 {wait} 秒...[/yellow]")
                    time.sleep(wait + 1)
                    continue

            # 处理 5xx 服务端错误
            if resp.status_code >= 500:
                backoff = (2 ** attempt) + random.uniform(0, 1)
                console.print(
                    f"[yellow]服务端错误 {resp.status_code}，"
                    f"{backoff:.1f}s 后重试 ({attempt+1}/{_MAX_RETRIES})[/yellow]"
                )
                time.sleep(backoff)
                continue

            # 主动检查剩余配额
            self._check_rate_limit(resp)

            resp.raise_for_status()
            return resp

        # 所有重试都失败
        raise requests.exceptions.ConnectionError(
            f"请求 {url} 在 {_MAX_RETRIES} 次重试后仍然失败"
        )

    def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{API_BASE}{path}" if path.startswith("/") else path
        resp = self._request("GET", url, params=params)
        return resp.json()

    def search_repos(self, keyword: str, language: str = None,
                     min_stars: int = 100, max_repos: int = 10) -> list[dict]:
        """搜索仓库，返回 [{full_name, stars, description, url}, ...]"""
        q = keyword
        if language:
            q += f" language:{language}"
        q += f" stars:>={min_stars}"

        data = self._get("/search/repositories", params={
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": min(max_repos, 100),
        })

        repos = []
        for item in data.get("items", [])[:max_repos]:
            repos.append({
                "full_name": item["full_name"],
                "stars": item["stargazers_count"],
                "description": item.get("description", ""),
                "url": item["html_url"],
            })
        return repos

    def get_contributors(self, repo_full_name: str,
                         max_count: int = 50) -> list[str]:
        """获取仓库贡献者用户名列表"""
        data = self._get(f"/repos/{repo_full_name}/contributors", params={
            "per_page": min(max_count, 100),
        })
        usernames = []
        for user in data:
            login = user.get("login", "")
            if login and not login.endswith("[bot]"):
                usernames.append(login)
        return usernames[:max_count]

    def get_pr_authors(self, repo_full_name: str,
                       max_count: int = 30) -> list[str]:
        """获取仓库 PR 作者用户名列表"""
        data = self._get(f"/repos/{repo_full_name}/pulls", params={
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "per_page": min(max_count, 100),
        })
        seen = set()
        usernames = []
        for pr in data:
            user = pr.get("user", {})
            login = user.get("login", "")
            if login and login not in seen and not login.endswith("[bot]"):
                seen.add(login)
                usernames.append(login)
        return usernames[:max_count]

    def get_user_info(self, username: str) -> dict:
        """获取用户详细信息"""
        data = self._get(f"/users/{username}")
        return {
            "username": data.get("login", ""),
            "name": data.get("name", ""),
            "email": data.get("email", ""),
            "bio": data.get("bio", ""),
            "company": data.get("company", ""),
            "blog": data.get("blog", ""),
            "public_repos": data.get("public_repos", 0),
            "followers": data.get("followers", 0),
        }

    def get_user_events_emails(self, username: str) -> list[str]:
        """从用户公开事件中提取 commit 邮箱"""
        try:
            events = self._get(f"/users/{username}/events/public", params={
                "per_page": 100,
            })
        except requests.HTTPError:
            return []

        emails = set()
        for event in events:
            if event.get("type") == "PushEvent":
                payload = event.get("payload", {})
                for commit in payload.get("commits", []):
                    author = commit.get("author", {})
                    email = author.get("email", "")
                    if email:
                        emails.add(email)
        return list(emails)
