# Merge PR Checklist

## 1. 平台与身份

先根据 remote 或 PR/MR URL 识别平台，然后执行 CLI 门禁：

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

GitHub 且 `gh` 可用时，平台对象必须使用 `gh`；查询字段、required checks 或原子合并条件无法由 `gh pr` 表达时使用 `gh api` / `gh api graphql`，普通 Git ref 的 fetch/push 和带 lease 删除继续使用 `git`。GitLab 且 `glab` 可用时执行相同平台工具约束。CLI 未认证、权限不足、仓库映射失败或网络失败属于待修复条件或阻塞，不得切换 browser、Computer Use 或网页登录。只有用户明确要求网页操作时才允许浏览器。

所有模式都需要获得：

- PR/MR URL、状态、作者、来源仓库、base/head 分支和 SHA。
- 标题、正文、关联 issue、labels、review、讨论和 requested changes。
- mergeability、required checks、仓库允许的合并方式、branch protection 和自动删除分支设置。

PR 处理模式另外获得提交列表、文件列表和完整 diff。交付合并模式不读取完整 diff。

PR 处理模式只看网页摘要或 `--stat` 不算完成评审。

### 模式判定

- 用户直接要求合并、处理、review、审核或检查指定 PR/MR：使用 PR 处理，即使 PR 作者是用户自己。
- 当前 `$commit` 或 `$resolve-issue` 为刚创建并已验证的精确 head SHA 携带验证上下文接力：使用交付合并。
- 已有 PR、跨任务恢复或缺少上层验证上下文：使用 PR 处理。

交付合并复用上层当前 head 的本地检查，跳过第 3 节；冲突或 head 内容变化时只补一次受影响本地检查。不得根据 PR 作者身份切换模式。

## 2. 不可信代码隔离

fork 或来源不受信任的 PR/MR 代码不得直接在带宿主凭据的环境执行。运行构建、测试、安装器或仓库脚本前：

- 使用一次性受限容器/沙箱，不挂载 SSH agent、Git credential helper、云凭据、用户配置和宿主敏感目录。
- 清除 token、secret 和认证环境变量，默认禁用网络；确需网络时只开放最小目标。
- 禁用仓库 hooks，不执行来源分支提供的任意 bootstrap 脚本。
- 只提供测试所需的最小文件和权限，结束后销毁环境。

无法建立可信隔离时，只做静态评审并报告“未运行不可信代码”；不能为了得到测试结果暴露宿主环境。

## 3. 评审清单

本节只用于 PR 处理。交付合并不执行本节；head/base 漂移或冲突解决不改变模式。

- 需求：改动是否解决正文或关联 issue 描述的问题，是否夹带无关修改。
- 正确性：正常路径、边界条件、失败路径、并发和幂等性是否合理。
- 安全：鉴权、权限、输入验证、secret、注入和敏感日志。
- 数据：schema、迁移、兼容性、事务、回滚和历史数据。
- 接口：API、配置、事件和依赖是否保持兼容。
- 测试：测试是否能在旧实现上失败、在新实现上通过；是否覆盖主要风险。
- 运维：部署顺序、监控、性能和故障恢复。

评审输出按严重级别排序，给出精确文件和行号。没有发现问题时明确说明剩余测试缺口。

## 4. 本地冲突集成

1. 记录远端 base/head SHA，获取最新 refs。
2. 保留用户现有工作区；在独立 branch/worktree 中处理。
3. 根据权限选择从 PR head 合入 base，或从 base 合入 PR head 创建替代请求。
4. 解决冲突后确认 `git diff --check` 通过，仓库中不存在冲突标记。
5. 冲突解决产生新内容后，两个模式都对 delta 运行一次受影响本地检查，并等待新 SHA 的 required checks。
6. 推送前重新查询平台 head/base SHA；任一发生影响合并结果的变化时停止并重新处理。
7. 推回原 head 后记录新的 head SHA，GitHub 复核 review/mergeability/branch protection，GitLab 重新等待该 SHA 对应的 required checks 和 review。

不要用强推或 `--force-with-lease` 更新贡献者分支的提交历史。普通 fast-forward push 失败时停止；重新基于最新 head 生成新提交，或创建替代 PR/MR。第 8 节对已合并同仓库 head 执行带 expected SHA 或 lease 的 ref 删除只用于并发保护，不属于内容更新；fork 分支仍不得删除。

## 5. 合并前检查

- 没有 unresolved conversation 或 requested changes。
- 当前精确 head 已有可复用的本地检查结果，且仓库 required checks 已成功并对应同一 SHA。
- PR/MR 仍为 open，base/head SHA 与评审时一致。
- 对权威 remote 执行最新 fetch，并在平台合并前先把本地目标分支同步到当前 `<remote>/<base>`。本地目标 ref 含独有提交、已经分叉、存在 Git 进行中状态或被无法协调的活跃写任务占用时，停止平台合并；不能把本地整合风险留到远端合并之后。
- 使用 Git 路径集合核对本地 staged、unstaged、未忽略 untracked 内容与预计目标更新：预计更新至少覆盖本地目标到最新远端 base 的变化，以及最新 base 到 PR/MR head 的变化。存在路径重叠或无法确认 rename/生成文件影响时，先归类、提交、迁移到明确任务分支或取得处置决定，再继续平台合并；不得自动 stash、reset 或提交归属不明内容。
- 本地未提交路径与预计目标更新完全不重叠时，记录目标 ref SHA、`git status --porcelain=v2 -z` 状态指纹和 worktree 归属，允许保留这些改动继续合并。脏工作树本身不是停止理由；预检的目标是证明合并后能够安全 fast-forward，而不是追求形式上的空工作树。
- 使用 expected head SHA 的平台原子合并条件；GitHub 可使用 GraphQL `expectedHeadOid` 或 REST merge `sha`，GitLab 使用支持 SHA 前置条件的 merge API。条件失败即重新读取平台状态，不因此切换模式。
- 合并方式符合仓库规范，commit message 不丢失 issue 关联。
- 数据库迁移、发布顺序和回滚方案已确认。

交付合并下，required checks pending 时等待。需要修改代码时仍保持交付合并模式，并对新 head 运行一次受影响本地检查。

## 6. 替代请求一致性

- 创建或实质改写替代 PR/MR 前已执行本 Skill 的平台文案规则；标题、正文和自定义小节默认使用简体中文，让不了解冲突背景的人也能看懂替代原因、实际纳入内容、验证和风险。
- 替代 PR/MR 正文记录原请求 URL 和实际纳入的 source head SHA。
- 替代请求不能继承原请求的 approval、required checks 或讨论解决状态；必须重新完成本地检查和平台闸门。
- 替代请求合并前再次查询原 source head；已前进时停止，重新评估 delta。
- 替代请求已合并后，关闭原请求前再次查询 source head。只有 source head 仍等于已纳入 SHA 时才关闭；否则保留原请求并说明哪些新增提交未被纳入。

## 7. 本地目标分支同步

平台确认合并成功并返回最终合并 SHA 后，必须把 PR/MR 的实际 base 拉取到本地对应目标分支，通常是 `main`：

1. 确认权威 remote 与 base，执行定向 fetch，并记录 `<remote>/<base>` 的最新 SHA；不要依赖合并前的 remote-tracking ref。
2. 验证刚 fetch 的远端目标 ref 包含平台返回的最终合并 SHA。若不包含，重新查询平台状态和 remote 映射，禁止更新错误仓库或错误分支。
3. 使用 `git worktree list --porcelain` 定位本地目标分支，并重新读取未提交内容、Git 进行中状态、ahead/behind 和状态指纹。预检后状态发生变化时重新做路径核对，不沿用旧的安全结论。
4. 目标分支已在 worktree 检出且本地 ref 是远端 ref 祖先时，在该 worktree 执行 `git merge --ff-only <remote>/<base>`。预检确认不重叠且指纹未变化的未提交改动可以保留；Git 若判定会覆盖本地内容并拒绝更新，保持现场并立即处理，不改用 stash、reset、rebase 或强制更新。
5. 目标分支未被任何 worktree 检出时，确认它没有独有提交且是远端 ref 的祖先，再用等价于 `git update-ref refs/heads/<base> <remote-sha> <old-local-sha>` 的 CAS 快进本地 ref。不要为了更新目标 ref 强制切走其他活跃分支，也不要绕过 worktree 更新一个已检出的分支。
6. 同步后确认本地目标分支 SHA 与本次 fetch 的 `<remote>/<base>` SHA 完全一致，且最终合并 SHA 是其祖先或等于它。若目标分支当前已检出，同时确认 HEAD 指向该 SHA、预检保留的未提交改动仍存在；若后续还有已归类的本地交付组，必须从这个最新目标分支建立或更新其工作分支。

本地同步是平台合并后的硬完成条件，不是可选清理。预检应在路径重叠、分叉或活跃写入时阻止平台合并；若 PR/MR 已被外部合并，或预检后发生竞态导致同步失败，当前流程必须保持未完成并继续协调，直到远端结果已经合入本地目标分支。禁止把“远端已合并、本地未收口”作为成功结论或正常停点。

## 8. 远端分支收口

用户授权合并默认包含合并后清理符合安全条件的同仓库 head 分支，无需再次要求“删除分支”。以下条件全部成立时必须删除：

- PR/MR 已成功合并，目标分支包含最终结果。
- head 分支不是默认分支或保护分支。
- 没有其他开放 PR/MR 引用该分支。
- 分支属于当前项目并具有删除权限，不是 fork 作者拥有的分支。
- 远端 ref 仍存在，且 SHA 精确等于合并时记录的 head SHA。
- 用户没有明确要求保留，且没有当前任务、开放 issue、agent、自动化或人工流程继续使用它的证据。

删除前重新读取 ref，并且只使用支持 expected SHA 或 lease 的删除路径绑定合并时记录的 head SHA，防止读取后出现并发提交却被误删。Git remote 可使用 `git push --force-with-lease=refs/heads/<head>:<head-sha> <remote> :refs/heads/<head>`；该 lease 只保护 ref 删除，不授权改写提交历史。平台自动删除已开启时仍验证 ref 确实消失；未开启时显式删除。没有安全删除路径或已确认缺少权限时报告未完成的清理阻塞；其他删除失败先修复权限、认证、工具或瞬时错误并重试，不能静默改成正常保留。

用户明确要求保留、fork 分支、默认/保护分支、其他开放 PR/MR 仍引用、权限或归属不清、存在明确活跃用途或远端 SHA 漂移时保留并报告证据。权限或归属能够继续核实时先核实；已确认无权删除时标记清理阻塞。除此之外，不得把“用户只要求合并”或“平台没开自动删除”作为保留理由。

删除后 fetch/prune 并重新读取平台 ref，确认远端与 remote-tracking ref 都已收口；若目标分支 ref 在清理期间前进，重新执行第 7 节的 fast-forward-only 同步与 SHA 验证。不把“分支删除成功”当作“合并成功”的替代证据。
