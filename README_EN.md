[中文](./README.md)

# GitHub Recruiter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![GitHub API](https://img.shields.io/badge/GitHub-API%20v3-181717.svg?logo=github)](https://docs.github.com/en/rest)

A CLI tool that discovers active developers from GitHub repositories, collects contact information, and sends recruitment emails automatically.

## How It Works

```
Input keyword → Search GitHub repos → Extract contributors/PR authors → Collect emails → Send emails
```

Email collection priority:
1. GitHub user's public email field
2. Commit author email from PushEvent
3. Regex match from user bio / blog

Automatically filters out `noreply@github.com` and other invalid emails.

## Installation

```bash
git clone https://github.com/yourname/github-recruiter.git
cd github-recruiter
pip install -e .
```

## Configuration

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with:
- GitHub Personal Access Token (requires `public_repo` scope)
- SMTP email settings (Gmail requires [App Passwords](https://support.google.com/accounts/answer/185833))

## Usage

### Search & Collect

```bash
# Search Python repos related to "agent" with 500+ stars
github-recruiter search "agent" --language python --min-stars 500

# Search LLM-related repos
github-recruiter search "LLM" --language python --min-stars 1000
```

### View Candidates

```bash
# View all
github-recruiter list

# Filter by status
github-recruiter list --status pending
github-recruiter list --status sent
```

### Send Emails

```bash
# Preview mode (no actual sending)
github-recruiter send --dry-run --limit 5

# Actually send
github-recruiter send --limit 10
```

### One-click Run

```bash
# Search + collect + preview
github-recruiter run "agent" --language python --dry-run

# Search + collect + send
github-recruiter run "agent" --language python --limit 20
```

### Statistics

```bash
github-recruiter stats
```

## Custom Email Templates

Edit `templates/default.txt` with supported variables:

| Variable | Description |
|----------|-------------|
| `{name}` | User's real name |
| `{username}` | GitHub username |
| `{repos}` | Associated repositories |
| `{keyword}` | Search keyword |
| `{from_name}` | Sender's name |
| `{email}` | Recipient's email |
| `{bio}` | User's bio |
| `{company}` | User's company |

The first line of the template must be `Subject: your subject line`.

## Notes

- GitHub API rate limit: 60/hour unauthenticated, 5000/hour with token
- Email sending has rate limiting and daily caps (configurable)
- Only uses publicly available information
- Automatically skips `noreply@github.com` addresses

## License

MIT
