---
name: merge-pr
description: 评审或合并已有 GitHub Pull Request、GitLab Merge Request。用于检查实现与 CI/review、处理冲突、按用户授权合并及清理关联分支；不用于从 issue 开始实现（用 resolve-issue）或仅提交本地改动（用 commit）。
---

# Merge PR

把“能不能合”与“怎么合”分开处理：先证明改动合理，再选择平台合并或本地冲突集成。

## 边界

- 从 issue 开始实现需求，使用 `$resolve-issue`。
- 本地提交和 AI 开发现场清理使用 `$commit`；本流程只决定 PR/MR 评审、冲突、合并和关联远端分支。
- 本流程只清理自己创建的本地现场，以及与已合并 PR/MR 一一对应且可证明安全的远端分支。
- 不绕过必需 review、CI、branch protection 或仓库合并策略。

## 合并闸门

只有 checklist 的需求、评审、测试、当前 head SHA、CI/review、权限和仓库策略闸门全部通过，且用户已授权合并时才继续。阻塞问题先按严重级别和文件/行号报告；安全边界和平台保护规则不能绕过。

## 工作流

执行前读取 [merge-checklist.md](references/merge-checklist.md)。

### 1. 定位 PR/MR

按 checklist 定位平台、项目、base/head、作者和最新 SHA，保护本地已有改动；不可信来源没有隔离环境时只做静态评审。

### 2. 完成评审

检查完整 diff、需求、正确性、安全、数据、兼容、测试和运维风险；先输出 actionable findings，没有阻塞问题时明确给出可合并结论和剩余风险。

### 3. 选择合并路径

- **无冲突**：等待必需检查通过，按仓库规则并绑定预期 head SHA 合并；条件不满足时重新评审。
- **有冲突且可更新原 head**：在隔离 worktree 中从最新 PR head 创建临时集成分支，把最新 base 合入该分支，按双方意图解决冲突并测试。只有实际 branch push 权限、保护规则和仓库政策均允许，且远端 head SHA 未变化时，才把冲突解决提交以普通 fast-forward push 推回原 head。
- **有冲突但不能更新原 head**：从最新 base 创建自有集成分支，合入 PR head 并解决冲突，推送后创建替代 PR/MR，正文关联原请求和冲突处理。替代请求合并前不关闭原请求。

默认用 merge 保留双方历史；只有仓库明确要求线性历史时才 rebase。禁止直接把未经平台检查的本地合并结果推到保护目标分支。base 在评审或解冲突期间前进时，重新检查 combined diff、mergeability 和相关测试，或进入仓库 merge queue；对数据迁移、安全边界等高风险改动，要求 merge queue 或 up-to-date checks。

### 4. 冲突处理

按 checklist 理解并解决每个冲突，验证 combined diff 和相关测试。产生新 head 后重新执行评审、CI 和 review 闸门；漂移或推送失败时重新基于最新状态处理，不升级为强推。

### 5. 合并与验证

通过支持 expected head SHA 的平台 API 或 merge queue 原子合并，记录最终 SHA，并确认平台状态、目标分支、必需检查和部署/迁移影响。

### 6. 清理分支与现场

仅在合并成功，或本流程创建的现场已被明确废弃并由新现场完整取代后清理：

- 本流程创建的临时 worktree 和本地集成分支交给 `$commit`，并提供 AI 所有权、活跃状态和指纹证据。
- 删除远端 head 前确认它属于当前项目、不是默认/保护分支、没有其他开放 PR/MR 使用，并且用户的合并请求包含清理意图。
- fork 中贡献者拥有的分支默认不删除；权限或归属不清时保留并报告。
- 若使用替代 PR/MR，在正文记录实际纳入的原 source head SHA，替代请求重新执行全部 review/CI 闸门。合并前和关闭原请求前都重新检查原 head；只有它仍等于已纳入 SHA 时才关闭原请求。若它已前进，保留原请求处理新增 delta。
- 本流程创建但因 head/base 漂移而废弃的替代请求、分支和 worktree，可以在确认未被引用且内容已被新现场取代后关闭/删除，并留下替代关系。

完成或暂停前调用 `$commit` 的“远端已完成”模式，只做本地盘点和安全清理，不再创建或合并 PR/MR；只把恢复该 PR/MR 必需的 AI 现场标记为活跃，用户或归属不明现场保持原样。

## 最终回复

必须包含：

- PR/MR URL、base/head、评审结论和主要风险
- CI、review 与本地验证结果
- 冲突文件、解决原则和冲突解决提交（如有）
- 合并方式、最终 SHA 和平台合并状态
- 关联远端分支的删除或保留结论与安全证据
- `$commit` 返回的本地仓库收口结果
