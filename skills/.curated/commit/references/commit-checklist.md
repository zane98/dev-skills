# Commit Checklist

## 1. 获取真实状态

从 skill 目录运行：

```bash
python3 scripts/git_cleanup.py inspect --repo <repo>
```

另外检查：

```bash
git -C <repo> remote -v
git -C <repo> status --short --branch
git -C <repo> diff
git -C <repo> diff --cached
git -C <repo> diff --check
git -C <repo> ls-files --others --exclude-standard
git -C <repo> status --short --ignored=matching
```

`--ignored` 输出仅用于了解本地开发环境，不是删除清单。读取托管平台的开放 issue/PR/MR，并确认是否有 live agent、自动化或人工流程正在使用某个现场。不要把 feature upstream 当作目标分支。

## 2. 分类标准

| 结论 | 必需证据 | 动作 |
|---|---|---|
| 交付 | 属于当前请求且通过 diff/测试检查 | stage、commit |
| 明确活跃 | 对应当前任务、开放 issue/PR/MR、用户指令或 live owner | 保留并报告归属 |
| AI 残留 | 有 AI 创建证据，且已交付、废弃、重复或过期 | 按指纹直接删除 |
| Ignored 本地环境 | 被 `.gitignore` 覆盖的构建产物、缓存、依赖或本地配置 | 原地保留；仅在用户明确点名路径要求删除时处理 |
| 用户/未知 | 用户创建，或没有充分的 AI 所有权证据 | 原地保留并报告，不读取敏感内容 |
| 阻塞 | 权限、工具或并发变化使删除无法完成 | 修复阻塞后继续，不改成保留 |

删除需要两份独立结论：它由 AI 创建，并且已经不活跃。名称、时间、dirty 状态或无法映射到任务都不能单独证明所有权。

## 3. 提交闸门

- staged 文件全部属于当前任务。
- 不重写已确认属于其他活跃任务的 index/hunk。
- 没有意外凭据、私钥、数据库转储或大文件。
- 已遵循仓库 commit message 规范。
- 已运行与改动匹配的测试；未运行项会被报告。

提交当前任务后再开始收口，避免把交付内容当作残留清掉。

## 4. 确定性删除

以下命令只用于已经分类为 `AI 残留` 的候选项。helper 的 inspect 输出包含 branch/stash SHA 和 worktree 状态指纹；每次删除都传回预期值，防止盘点后其他进程修改现场。

删除本地分支：

```bash
python3 scripts/git_cleanup.py delete-branch <branch> --repo <repo> --expect-sha <sha> --protect <target>
```

删除 stash：先按 selector 数字倒序处理，每次使用最新 inspect 核对 SHA。

```bash
python3 scripts/git_cleanup.py drop-stash 'stash@{n}' --repo <repo> --expect-sha <sha>
```

删除额外 worktree，包括 dirty 或中断现场：

```bash
python3 scripts/git_cleanup.py remove-worktree <path> --repo <repo> --expect-head <sha> --expect-status <fingerprint>
```

锁定但确认不活跃的 worktree 增加 `--unlock`。helper 禁止删除主 worktree。

清空 AI 所有且需要保留的 worktree 中已确认无用途的 tracked 改动和未忽略 untracked 内容：

```bash
python3 scripts/git_cleanup.py clean-worktree <path> --repo <repo> --expect-head <sha> --expect-status <fingerprint>
```

该命令使用 `git clean -ffd`，必须保留所有 ignored 内容，不得增加 `-x`。存在无用的 merge/rebase/cherry-pick/revert/bisect 状态时增加 `--abort-operation`。其他需要保留的未忽略路径可用重复的 `--exclude <pattern>` 排除；用户内容或归属不明内容不得传给清理命令。

删除单独临时路径：

```bash
python3 scripts/git_cleanup.py fingerprint-path <path> --repo <repo>
python3 scripts/git_cleanup.py delete-path <path> --repo <repo> --expect-fingerprint <fingerprint>
```

helper 不创建 bundle、patch、recovery ref、archive 或 quarantine。

## 5. 删除顺序与并发

以下顺序只处理已分类为 `AI 残留` 的候选项：

1. 非目标 worktree。
2. 不活跃本地分支。
3. 不活跃 stash，selector 倒序。
4. AI 所有 worktree 中已确认无用途的 tracked 改动和未忽略残留；保留 ignored 本地环境。
5. `git fetch --prune` 清理 remote-tracking refs。

任何 SHA、HEAD 或状态指纹不匹配都表示现场已变化。重新 inspect、重新分类，然后继续；不要跳过 CAS 检查。

## 6. 最终验收

```bash
python3 scripts/git_cleanup.py inspect --repo <repo>
git -C <repo> status --short --branch
git -C <repo> stash list
git -C <repo> worktree list --porcelain
git -C <repo> branch -vv
```

验收标准：当前交付已提交且没有当前任务的 Git 残留；ignored 本地环境保持原样；保留的 AI 现场都有活跃任务；用户或归属不明现场保持原样并已报告；不存在本流程创建的归档或恢复副本。
