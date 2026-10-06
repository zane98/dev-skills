# Commit Checklist

清理范围、授权和完成条件以 [SKILL.md](../SKILL.md) 为准。本文件只提供执行检查与工具契约。

## 1. 平台与现场

根据 `git remote -v` / `git remote get-url` 识别平台和真实合并目标，再检查对应 CLI：

```bash
# GitHub
command -v gh
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef

# GitLab
command -v glab
glab auth status
glab repo view
```

普通 ref 传输使用 `git`，平台操作使用对应 CLI/API。CLI、权限和认证异常按主文件处理，不能擅自打开网页认证。

从 skill 目录检查全部现场，并按本任务归属分类：

```bash
python3 scripts/git_cleanup.py inspect --repo <repo> --target <verified-target-ref-or-sha>
git -C <repo> status --short --branch
git -C <repo> diff
git -C <repo> diff --cached
git -C <repo> diff --check
git -C <repo> ls-files --others --exclude-standard
```

`inspect` 返回各 worktree 的状态指纹、分支 SHA、stash SHA 和临时路径候选。`task_path_candidates` 包含 `.codex/tmp/*`、`.claude/worktrees/*` 及系统临时目录中的 `<repo>-*` / `codex-<repo>-*`。候选只是发现线索：结合本任务操作记录、开放 issue/PR/MR、用户指令和 live owner 判断所有权。普通 ignored 环境及其他任务现场保留；不能依据名称删除，也不能将它们自动加入任务清单。

`--target` 将目标锁定为输出的 `target_sha`，为本地 branch 和各 worktree HEAD 返回 `head_in_target` 与 `unique_commits`（目标不可达的提交 SHA）；另报告 `dirty` 与 `has_ignored`。目标不存在时报错；缺失的已注册 worktree 报告状态未知。helper 不 fetch、不查询平台、不删除；省略 `--target` 时仍可做原始盘点，不能据此回答合并状态。

报告覆盖全仓，清理范围仍按下表：

- 使用权威目标的已验证 SHA；仅有旧本地 ref 时注明新鲜度未核实。对所有额外本地分支/worktree核对目标可达性；以 `git ls-remote --heads <remote>` 读取同仓库真实远端开发分支，不能把陈旧 remote-tracking ref 当作仍存在的远端分支。远端 SHA、本地对象、PR/MR 或 owner 无法核实时，报告未知及原因。
- `head_in_target=true` 只证明当前已提交 HEAD 的历史已纳入该目标；`false` 或存在 `unique_commits` 不证明未合并，squash/rebase 需要精确 repo、base、source head、merge SHA 与平台状态及 patch/结果证据。不要仅凭分支名匹配历史 PR，或把已纳入目标等同可删除。
- 历史 PR/MR 已合并时分别核对当前 head：等于已纳入 source head可复用该证据；source head 是当前 head 的祖先时，检查其后的新 delta；发生其他漂移时标明未知。再查 dirty/ignored 内容与活跃 owner，原 PR 已合并不能覆盖后续成果。只有精确匹配且有未纳入目标证据的开放 PR/MR 才标为尚未合并；证据不足不猜测。

恢复原任务时，原任务/附件 metadata 应将 repo、PR/MR、base/head SHA、branch/worktree 路径和 owner 绑定。明确接管且 owner 已释放后，才能把其现场纳入本任务；发现新 delta、混合 WIP 或来源不明时保留并列明，不把全仓报告当作全仓删除授权。

| 项目 | 进入本任务清单的证据 | 删除前要求 |
|---|---|---|
| 本地分支 | 本次创建或明确接管 | 非目标分支，内容已交付/等价或有明确废弃授权，SHA 未变 |
| stash | 本次创建或明确接管，记录完整 SHA | 内容已交付/无用途或有明确废弃授权，当前 selector 仍匹配该 SHA |
| 额外 worktree | 本次创建或明确接管 | 无活跃 owner，全部内容可删除，HEAD 和状态指纹未变 |
| 临时路径 | 操作记录证明本任务创建且应移除 | 用途结束，内容可删除，路径指纹未变 |

已在清单中的资源发现独有内容或活跃 owner 时保留并报告未完成，不能删清单项来绕过验收。只有全仓清理授权才将盘点的全部现场作为待处置范围。

## 2. 每组交付检查

- staged 文件/hunk 只属于当前组；无未知内容、其他任务改动、secret 或意外大文件。
- 已按仓库约定提交，并完成风险匹配的实际验证；记录明确未运行的检查。
- 接力上下文含仓库、目标分支、已验证 base SHA、head 分支、精确 head SHA、评审范围和测试结果。
- 普通 push 后验证远端 SHA；PR/MR 与仓库/head/base/SHA 匹配，描述符合真实 diff。
- 调用 `$merge-pr` 的“交付合并”模式，显式传递接力上下文及符合安全条件的同仓库远端 head 清理授权。
- 平台 required checks、review、冲突、branch protection、merge queue 和原子合并闸门均由 `$merge-pr` 核对；上下文仍有效时不重复本地评审/测试。
- 确认平台合并状态、最终 merge SHA 和远端 head 处置；在安全 checkout 中 fast-forward-only 同步目标。多个组从最新目标依次交付，全部完成后再最终清理。

## 3. 删除命令与顺序

以下命令有删除副作用。只有完成主文件的范围、所有权及可删除判断后才能调用；helper 的指纹比较本身不证明这些事实。

已合并的依据是平台状态、精确 head/merge SHA 与目标分支可达性；squash/rebase 后不能只靠 `git branch --merged`。另行核对分支新增提交、staged/unstaged/untracked 与需保留的 ignored 内容；历史 PR 已合并不证明当前 worktree 的全部内容已交付。

### App-managed worktree

用 `list_artifacts` 确认本任务附件 identity、路径和管理归属，再用 `archive_worktree` 的 exact identity 归档；不以 `git worktree remove` 或直接删目录代替官方生命周期。先释放活跃 owner，复核 HEAD/状态并保存需要保留的 ignored 文件：官方归档的快照不包含普通 ignored 内容。归档只处理本地现场，分支与远端交付仍须分别核对。

工具拒绝 primary、pinned、shared、存在 submodule/embedded repo 或不可用时，保留现场并报告具体清理阻塞，不绕过工具。成功后重查 artifacts、Git 注册和磁盘路径，报告 `已归档，checkout 已移除`；可恢复快照不代表已合并，也不要求删除它来伪造零残留。验收仍使用原路径，不能因已经提交归档请求就从 manifest 移除该项。

### 普通 Git 现场

```bash
# 先移除本任务额外 worktree，再删分支
python3 scripts/git_cleanup.py remove-worktree <path> --repo <repo> --expect-head <sha> --expect-status <fingerprint>
python3 scripts/git_cleanup.py delete-branch <branch> --repo <repo> --expect-sha <sha> --protect <target>

# helper 仅支持唯一 stash entry；多 entry 不删除，先完整审计并报告限制
python3 scripts/git_cleanup.py drop-stash 'stash@{0}' --repo <repo> --expect-sha <sha>

# 路径必须在仓库内，或是 helper 可发现的仓库命名系统临时路径
python3 scripts/git_cleanup.py fingerprint-path <path> --repo <repo>
python3 scripts/git_cleanup.py delete-path <path> --repo <repo> --expect-fingerprint <fingerprint>
```

`delete-branch` 拒绝已检出的分支，并用 Git 原生 expected-old ref 事务绑定删除 SHA；分支配置不属于该事务，helper 不自动删除，避免误删随后重建同名分支的新 upstream。`drop-stash` 仅支持已验证的 files ref backend 中唯一的 `stash@{0}`：使用 Git 原生 prepare/commit 事务持锁复核 SHA 与完整 reflog，再由 Git 删除。多 entry 缺少原生 expected-entry 删除接口，因此拒绝；reftable、锁冲突、异常 reflog 或状态漂移也拒绝，不手写 refs/reflog 或回退到无 SHA 约束的 `git stash drop`。失败后重新读取现场，不依据此前 selector 重试或宣称删除已完成。

全 worktree 重置仅限已独占、全部内容可删除的范围内 worktree；共享主 checkout 或混合 WIP 禁用：

```bash
python3 scripts/git_cleanup.py clean-worktree <path> --repo <repo> --expect-head <sha> --expect-status <fingerprint>
```

该命令执行 `reset --hard` 和清除未忽略内容。存在 Git 进行中状态时默认拒绝；只有明确确认中止属于授权范围才加 `--abort-operation`。移除 locked worktree 同理，确认锁的 owner 已释放后才用 `--unlock`。任何 SHA/状态变化均需重新盘点和判断，不升级为无条件删除。

`git fetch --prune` 可移除陈旧 remote-tracking refs，真实远端分支按 `$merge-pr` 规则处理；helper 不处理远端交付。

## 4. 只读任务范围验收

在清理前根据任务记录创建 JSON manifest；将其保存在不会随本任务资源删除的审计位置，`--repo` 使用清理后仍存在的主 checkout；验收后作为结果记录。以下为格式示例，必须替换成真实资源，不得用示例值制造成功：

```json
{
  "version": 1,
  "repo": "/absolute/repo",
  "task": "当前任务标识",
  "branches": ["codex/example"],
  "stash_shas": [],
  "worktrees": ["/absolute/task-worktree"],
  "temp_paths": ["/absolute/repo/.codex/tmp/task-artifact"]
}
```

- 七个字段全部必填；未知字段、重复键/项、错误类型和缺失字段均拒绝。
- `repo` 必须是匹配 `--repo` 的绝对路径；`task` 必须非空。`branches` 使用本地分支名，不使用完整 ref；`stash_shas` 使用完整小写 SHA，不使用会漂移的 selector。
- `worktrees`、`temp_paths` 使用规范化绝对路径，不含 `..`，不指向仓库或文件系统根；worktree 同时检查磁盘路径和 Git 注册记录，悬空 symlink 也算残留。
- 四个资源列表全部为空时默认拒绝。若任务确实没有待移除资源，可显式增加非空 `empty_scope_reason`；结果显示零资源验证和该理由，不能用来证明实际资源已清理。有资源时禁止该字段。
- 本命令不检查共享主 checkout 的其他 WIP、其他分支/stash/worktree，不删除任何内容。遗漏清单项无法被它发现，清单完整性必须通过任务记录与最终盘点核对。

```bash
python3 scripts/git_cleanup.py verify-task-closeout --repo <repo> --manifest <scope.json>
```

通过时退出码 `0`，输出 `verified: true`、`mode: task`、各资源计数及明确的证明边界；清单无效或仍有资源退出码 `2`。它只证明 manifest 所列资源不存在，不证明清单完整、task diff 已交付、远端交付或全仓干净。结合第 2 节的远端证据与任务 diff 验证才能报告本任务完成。

## 5. 明确全仓清理时的额外验收

```bash
python3 scripts/git_cleanup.py verify-closeout --repo <repo> --target <target>
```

此命令保持原有全仓契约：仅目标本地分支和主 worktree，当前位于目标分支，stash/进行中状态/tracked 改动/未忽略内容均为空，自动发现的任务临时候选为空。普通 ignored 环境保留。它不验证远端合并或目标同步，需另用 Git/平台证据确认。

全仓 verifier 失败不能换成任务 verifier 后宣告全仓完成；默认任务 verifier 通过也不能被描述为全仓清零。其他活跃任务导致全仓不能安全清理时，报告全仓未完成并保留其现场。
