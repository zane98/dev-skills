# Merge PR Checklist

## 1. 平台与身份

优先使用仓库已配置的托管平台 CLI/API。GitHub 常用 `gh`，GitLab 常用 `glab`；使用前检查登录态和当前仓库映射。

需要获得：

- PR/MR URL、状态、作者、来源仓库、base/head 分支和 SHA。
- 标题、正文、关联 issue、labels、review、讨论和 requested changes。
- 提交列表、文件列表、完整 diff、CI/checks 和 mergeability。
- 仓库允许的合并方式、branch protection 和自动删除分支设置。

只看网页摘要或 `--stat` 不算完成评审。

## 2. 不可信代码隔离

fork 或来源不受信任的 PR/MR 代码不得直接在带宿主凭据的环境执行。运行构建、测试、安装器或仓库脚本前：

- 使用一次性受限容器/沙箱，不挂载 SSH agent、Git credential helper、云凭据、用户配置和宿主敏感目录。
- 清除 token、secret 和认证环境变量，默认禁用网络；确需网络时只开放最小目标。
- 禁用仓库 hooks，不执行来源分支提供的任意 bootstrap 脚本。
- 只提供测试所需的最小文件和权限，结束后销毁环境。

无法建立可信隔离时，只做静态评审并报告“未运行不可信代码”；不能为了得到测试结果暴露宿主环境。

## 3. 评审清单

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
5. 查看 merge commit 前后的 combined diff，运行相关测试。
6. 推送前重新查询平台 head/base SHA；任一发生影响合并结果的变化时停止并重新处理。
7. 推回原 head 后记录新的 head SHA，重新等待该 SHA 对应的 required checks 和 review。

不要向贡献者分支使用强推或 `--force-with-lease`。普通 fast-forward push 失败时停止；重新基于最新 head 生成新提交，或创建替代 PR/MR。

## 5. 合并前检查

- 没有 unresolved conversation 或 requested changes。
- 必需 CI 已成功且每个 required check 对应当前精确 head SHA；pending 时等待，失败时分析而不是绕过。
- PR/MR 仍为 open，base/head SHA 与评审时一致。
- 使用 expected head SHA 的平台原子合并条件；GitHub 可使用 GraphQL `expectedHeadOid` 或 REST merge `sha`，GitLab 使用支持 SHA 前置条件的 merge API。条件失败即重新读取和评审。
- 合并方式符合仓库规范，commit message 不丢失 issue 关联。
- 数据库迁移、发布顺序和回滚方案已确认。

## 6. 替代请求一致性

- 替代 PR/MR 正文记录原请求 URL 和实际纳入的 source head SHA。
- 替代请求不能继承原请求的 approval、讨论解决状态或 CI；必须重新完成全部闸门。
- 替代请求合并前再次查询原 source head；已前进时停止，重新评估 delta。
- 替代请求已合并后，关闭原请求前再次查询 source head。只有 source head 仍等于已纳入 SHA 时才关闭；否则保留原请求并说明哪些新增提交未被纳入。

## 7. 远端分支删除条件

以下条件必须全部成立：

- PR/MR 已成功合并，目标分支包含最终结果。
- head 分支不是默认分支或保护分支。
- 没有其他开放 PR/MR 引用该分支。
- 分支属于当前项目或用户明确拥有删除权限；fork 作者分支默认保留。
- 用户请求包含合并后的分支清理，或平台已有明确的自动删除策略。

删除后 fetch/prune 并验证平台状态，不把“分支删除成功”当作“合并成功”的替代证据。
