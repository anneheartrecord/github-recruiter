[English](./README_EN.md)

# GitHub Recruiter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![GitHub API](https://img.shields.io/badge/GitHub-API%20v3-181717.svg?logo=github)](https://docs.github.com/en/rest)

从 GitHub 仓库中发现活跃开发者，自动采集联系方式并发送招聘邮件的 CLI 工具。

## 工作原理

```
输入关键词 → 搜索 GitHub 仓库 → 提取贡献者/PR 作者 → 采集邮箱 → 自动发送邮件
```

邮箱采集优先级：
1. GitHub 用户公开 email 字段
2. PushEvent 中的 commit author email
3. 用户 bio / blog 中的邮箱正则匹配

自动过滤 `noreply@github.com` 等无效邮箱。

## 安装

```bash
git clone https://github.com/yourname/github-recruiter.git
cd github-recruiter
pip install -e .
```

## 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入：
- GitHub Personal Access Token（需要 `public_repo` scope）
- SMTP 邮箱配置（Gmail 需要[应用专用密码](https://support.google.com/accounts/answer/185833)）

## 使用

### 搜索并采集

```bash
# 搜索 "agent" 相关的 Python 仓库，最低 500 stars
github-recruiter search "agent" --language python --min-stars 500

# 搜索 "LLM" 相关仓库
github-recruiter search "LLM" --language python --min-stars 1000
```

### 查看候选人

```bash
# 查看全部
github-recruiter list

# 按状态过滤
github-recruiter list --status pending
github-recruiter list --status sent
```

### 发送邮件

```bash
# 预览模式（不实际发送）
github-recruiter send --dry-run --limit 5

# 实际发送
github-recruiter send --limit 10
```

### 一键执行

```bash
# 搜索 + 采集 + 预览发送
github-recruiter run "agent" --language python --dry-run

# 搜索 + 采集 + 实际发送
github-recruiter run "agent" --language python --limit 20
```

### 统计信息

```bash
github-recruiter stats
```

## 自定义邮件模板

编辑 `templates/default.txt`，支持以下变量：

| 变量 | 说明 |
|------|------|
| `{name}` | 用户真实姓名 |
| `{username}` | GitHub 用户名 |
| `{repos}` | 关联的仓库名 |
| `{keyword}` | 搜索关键词 |
| `{from_name}` | 发件人姓名 |
| `{email}` | 收件人邮箱 |
| `{bio}` | 用户 bio |
| `{company}` | 用户公司 |

模板第一行必须是 `Subject: 邮件标题`。

## 注意事项

- GitHub API 未认证限速 60 次/小时，认证后 5000 次/小时
- 内置请求延迟 + 指数退避重试 + Rate Limit 自动等待，不会因请求过快而崩溃
- 邮件发送有频率控制和每日上限，可在配置文件中调整
- 只使用公开信息，尊重用户隐私设置
- 遇到 `noreply@github.com` 会自动跳过

## 效果展示

### 搜索采集

```bash
$ github-recruiter search "kubernetes" --language go --min-stars 500

搜索关键词: kubernetes
限定语言: go
最低 Stars: 500

找到 5 个仓库:

  ⭐ 121491  kubernetes/kubernetes
  ⭐  62470  traefik/traefik
  ⭐  60611  minio/minio
  ⭐  51677  etcd-io/etcd
  ⭐  38077  istio/istio

提取贡献者: kubernetes/kubernetes
  贡献者: 20, PR 作者: 10, 去重后: 30

提取贡献者: traefik/traefik
  贡献者: 20, PR 作者: 7, 去重后: 26

提取贡献者: minio/minio
  贡献者: 20, PR 作者: 10, 去重后: 30

提取贡献者: etcd-io/etcd
  贡献者: 19, PR 作者: 4, 去重后: 22

提取贡献者: istio/istio
  贡献者: 20, PR 作者: 3, 去重后: 22

总计 130 个独立用户

  ✅ user_a → u***a@company.io
  ✅ user_b → u***b@gmail.com
  ⬜ user_c → 无公开邮箱
  ✅ user_d → u***d@outlook.com
  ⬜ user_e → 无公开邮箱
  ...

采集完成！新增 122 个候选人，其中 57 人有邮箱
```

### 查看候选人

```bash
$ github-recruiter list

                                              候选人列表
┏━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ ID   ┃ 用户名        ┃ 姓名                 ┃ 邮箱             ┃ 仓库       ┃ 关键词     ┃ 状态    ┃ 采集时间         ┃
┡━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ 130  │ user_a        │ Alice A.             │ a***@company.io  │ kubernetes │ kubernetes │ pending │ 2026-04-05 02:57 │
│ 129  │ user_b        │ Bob B.               │ b***@redhat.com  │ traefik    │ kubernetes │ pending │ 2026-04-05 02:57 │
│ 128  │ user_c        │ Charlie C.           │ 无               │ minio      │ kubernetes │ pending │ 2026-04-05 02:56 │
│ 127  │ user_d        │ David D.             │ d***@gmail.com   │ istio      │ kubernetes │ pending │ 2026-04-05 02:56 │
│ 126  │ user_e        │ Eve E.               │ 无               │ etcd       │ kubernetes │ pending │ 2026-04-05 02:55 │
│ ...  │ ...           │ ...                  │ ...              │ ...        │ ...        │ ...     │ ...              │
│ 1    │ user_z        │ Zara Z.              │ z***@traefik.io  │ traefik    │ kubernetes │ pending │ 2026-04-05 02:33 │
└──────┴───────────────┴──────────────────────┴──────────────────┴────────────┴────────────┴─────────┴──────────────────┘
```

> 以上输出已脱敏处理，实际使用时会显示真实的用户名和邮箱地址。

## License

MIT
