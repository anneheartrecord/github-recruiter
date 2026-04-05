import json
import click
from rich.console import Console
from rich.table import Table

from .config import load_config
from .db import get_db, upsert_candidate, get_candidates
from .github_api import GitHubAPI
from .email_finder import find_email_with_info
from .mailer import send_to_candidates

console = Console()


@click.group()
@click.option("--config", "-c", default="config.yaml", help="配置文件路径")
@click.pass_context
def cli(ctx, config):
    """GitHub Recruiter - 从 GitHub 仓库中发现人才并自动触达"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.argument("keyword")
@click.option("--language", "-l", default=None, help="限定编程语言，如 python/go/rust")
@click.option("--min-stars", "-s", default=None, type=int, help="最低 star 数")
@click.option("--max-repos", "-r", default=None, type=int, help="最多搜索几个仓库")
@click.option("--max-contributors", "-n", default=None, type=int, help="每个仓库最多提取几个贡献者")
@click.pass_context
def search(ctx, keyword, language, min_stars, max_repos, max_contributors):
    """搜索关键词相关仓库并采集贡献者信息"""
    config = load_config(ctx.obj["config_path"])
    search_cfg = config["search"]

    min_stars = min_stars or search_cfg["min_stars"]
    max_repos = max_repos or search_cfg["max_repos"]
    max_contributors = max_contributors or search_cfg["max_contributors"]

    api = GitHubAPI(config["github"]["token"])
    conn = get_db()

    # 1. 搜索仓库
    console.print(f"\n[bold]搜索关键词: [cyan]{keyword}[/cyan][/bold]")
    if language:
        console.print(f"限定语言: {language}")
    console.print(f"最低 Stars: {min_stars}\n")

    repos = api.search_repos(keyword, language=language,
                             min_stars=min_stars, max_repos=max_repos)

    if not repos:
        console.print("[yellow]未找到匹配的仓库[/yellow]")
        return

    console.print(f"找到 [green]{len(repos)}[/green] 个仓库:\n")
    for repo in repos:
        console.print(f"  ⭐ {repo['stars']:>6}  [cyan]{repo['full_name']}[/cyan]")

    # 2. 提取贡献者
    all_usernames = set()
    for repo in repos:
        console.print(f"\n[bold]提取贡献者: {repo['full_name']}[/bold]")

        contributors = api.get_contributors(repo["full_name"], max_count=max_contributors)
        pr_authors = api.get_pr_authors(repo["full_name"], max_count=max_contributors // 2)

        repo_users = set(contributors) | set(pr_authors)
        console.print(f"  贡献者: {len(contributors)}, PR 作者: {len(pr_authors)}, 去重后: {len(repo_users)}")
        all_usernames |= repo_users

    console.print(f"\n[bold]总计 {len(all_usernames)} 个独立用户[/bold]\n")

    # 缓存每个仓库的贡献者，避免重复请求
    repo_contributors_cache = {}
    for repo in repos:
        repo_contributors_cache[repo["full_name"]] = set(
            api.get_contributors(repo["full_name"], max_count=max_contributors)
        )

    # 3. 采集邮箱并入库
    new_count = 0
    email_count = 0
    with console.status("[bold green]采集用户信息...") as status:
        for i, username in enumerate(all_usernames, 1):
            status.update(f"[bold green]采集中 ({i}/{len(all_usernames)}): {username}")

            info = find_email_with_info(api, username)

            # 找到这个用户关联的仓库（使用缓存）
            user_repos = []
            for repo in repos:
                if username in repo_contributors_cache.get(repo["full_name"], set()):
                    user_repos.append(repo["full_name"])

            if not user_repos:
                user_repos = [repos[0]["full_name"]]

            is_new = upsert_candidate(
                conn, username=info["username"], name=info["name"],
                email=info["email"], bio=info["bio"],
                company=info["company"], blog=info["blog"],
                repos=user_repos, keyword=keyword
            )

            if is_new:
                new_count += 1
            if info["email"]:
                email_count += 1
                console.print(f"  ✅ {username} → {info['email']}")
            else:
                console.print(f"  ⬜ {username} → [dim]无公开邮箱[/dim]")

    conn.close()

    console.print(f"\n[bold green]采集完成！[/bold green]")
    console.print(f"  新增用户: {new_count}")
    console.print(f"  有邮箱: {email_count}")
    console.print(f"  无邮箱: {len(all_usernames) - email_count}")


@cli.command("list")
@click.option("--status", "-s", type=click.Choice(["pending", "sent", "failed", "skipped"]),
              default=None, help="按状态过滤")
@click.pass_context
def list_candidates(ctx, status):
    """查看已采集的候选人列表"""
    conn = get_db()
    candidates = get_candidates(conn, status=status)
    conn.close()

    if not candidates:
        console.print("[yellow]暂无候选人数据[/yellow]")
        return

    table = Table(title="候选人列表")
    table.add_column("ID", style="dim", width=4)
    table.add_column("用户名", style="cyan")
    table.add_column("姓名")
    table.add_column("邮箱", style="green")
    table.add_column("仓库")
    table.add_column("关键词", style="magenta")
    table.add_column("状态")
    table.add_column("采集时间", style="dim")

    for c in candidates:
        repos = json.loads(c.get("repos", "[]"))
        repos_str = ", ".join(r.split("/")[-1] for r in repos[:2])
        if len(repos) > 2:
            repos_str += f" +{len(repos)-2}"

        status_style = {
            "pending": "[yellow]pending[/yellow]",
            "sent": "[green]sent[/green]",
            "failed": "[red]failed[/red]",
            "skipped": "[dim]skipped[/dim]",
        }.get(c["status"], c["status"])

        table.add_row(
            str(c["id"]),
            c["username"],
            c.get("name") or "-",
            c.get("email") or "[dim]无[/dim]",
            repos_str,
            c.get("keyword", ""),
            status_style,
            c.get("found_at", "")[:16],
        )

    console.print(table)
    console.print(f"\n共 {len(candidates)} 条记录")


@cli.command()
@click.option("--dry-run", is_flag=True, help="仅预览，不实际发送")
@click.option("--limit", "-n", default=None, type=int, help="限制发送数量")
@click.pass_context
def send(ctx, dry_run, limit):
    """发送邮件给待处理的候选人"""
    config = load_config(ctx.obj["config_path"])
    conn = get_db()

    candidates = get_candidates(conn, status="pending")
    # 只选有邮箱的
    candidates = [c for c in candidates if c.get("email")]

    if limit:
        candidates = candidates[:limit]

    if not candidates:
        console.print("[yellow]没有待发送的候选人（可能都没有邮箱或已发送）[/yellow]")
        conn.close()
        return

    console.print(f"\n{'[DRY RUN] ' if dry_run else ''}准备发送 [bold]{len(candidates)}[/bold] 封邮件\n")

    stats = send_to_candidates(
        conn, candidates,
        smtp_config=config["smtp"],
        sending_config=config["sending"],
        dry_run=dry_run,
    )

    conn.close()

    console.print(f"\n[bold]发送结果:[/bold]")
    console.print(f"  ✅ 成功: {stats['sent']}")
    console.print(f"  ❌ 失败: {stats['failed']}")
    console.print(f"  ⏭️  跳过: {stats['skipped']}")


@cli.command()
@click.argument("keyword")
@click.option("--language", "-l", default=None, help="限定编程语言")
@click.option("--min-stars", "-s", default=None, type=int, help="最低 star 数")
@click.option("--dry-run", is_flag=True, help="仅预览邮件，不实际发送")
@click.option("--limit", "-n", default=None, type=int, help="限制发送数量")
@click.pass_context
def run(ctx, keyword, language, min_stars, dry_run, limit):
    """一键执行：搜索 → 采集 → 发送"""
    # 先执行搜索
    ctx.invoke(search, keyword=keyword, language=language, min_stars=min_stars)

    # 再执行发送
    console.print("\n" + "=" * 50)
    console.print("[bold]开始发送邮件...[/bold]\n")
    ctx.invoke(send, dry_run=dry_run, limit=limit)


@cli.command()
@click.pass_context
def stats(ctx):
    """查看统计信息"""
    conn = get_db()

    all_candidates = get_candidates(conn)
    pending = [c for c in all_candidates if c["status"] == "pending"]
    sent = [c for c in all_candidates if c["status"] == "sent"]
    failed = [c for c in all_candidates if c["status"] == "failed"]
    with_email = [c for c in all_candidates if c.get("email")]

    from .db import get_today_send_count
    today_sent = get_today_send_count(conn)
    conn.close()

    console.print("\n[bold]📊 统计信息[/bold]\n")
    console.print(f"  总候选人: {len(all_candidates)}")
    console.print(f"  有邮箱:   {len(with_email)}")
    console.print(f"  待发送:   {len(pending)}")
    console.print(f"  已发送:   {len(sent)}")
    console.print(f"  发送失败: {len(failed)}")
    console.print(f"  今日已发: {today_sent}")


if __name__ == "__main__":
    cli()
