# Plan Template

## 使用原则

- 默认一个开发目标一个计划文件；删除不适用章节，不为完整感制造目录或 shard。
- 计划只保存开发输出、依赖、开发 blocker 和必要决策；未提交、未部署或未线上验证不属于开发 blocker，不影响已完成任务的 done 状态。
- 计划目录根层只保存活跃计划；完成后移入 `done/`，同时更新旧入口和索引，不能遗留指向旧 doing 版本的当前入口。没有活跃计划时根层保持空，不保留已完成 overview、progress、umbrella 或 index。
- 不写验证列、验收清单、证据表、完成后提醒、执行日志或测试结果。
- 不创建 `QA/VERIFY/ACCEPT/REL/MANUAL` 任务。测试代码或测试基础设施是仓库产出时使用 `TEST-*`；运行检查由 `$development` 在执行时完成。
- 人工验收、浏览器走查、截图对比、生产发布、灰度和线上观察留在对话、PR/Issue、Runbook 或发布系统。

```md
# {需求名} 开发计划

## 当前状态

- 最后更新：{YYYY-MM-DD}
- 开发状态：todo / doing / blocked / done / cancelled
- 当前实现任务：{TASK-ID / 无}
- 开发阻塞：无 / {缺失的开发输入、解除条件、责任人}

## 目标与边界

{一句话说明要交付的产品或技术结果}

- 已确认事实：
- 可逆假设：
- 待决策项：{只保留会改变实现方案的决策}
- 非目标：

## 影响范围

- 契约/API：
- 数据/schema：
- 后端：
- 前端/客户端：
- 权限/幂等/兼容：
- 缓存/队列/可观测性：
- 测试资产：{仅新增或修改的测试代码、fixture、工具；无则删除}
- 长期文档：{只列权威产品/技术文档变更；无则删除}

## 设计实现映射（按需）

只有存在 Figma 或明确设计输入时保留。这里只记录实现映射，不记录截图、像素 diff 或人工验收结果。

| 设计来源/节点 | 页面或组件状态 | 目标代码 | 实现要点 |
|---|---|---|---|
| {frame/node} | {正常/加载/空/失败/交互} | {route/component} | {结构、token、资产和行为映射} |

## 实现任务

| ID | 实现输出 | 状态 | 负责人 | 依赖 | 影响范围 |
|---|---|---|---|---|---|
| API-01 | {公共契约、字段、错误和兼容策略} | todo | {owner} | 无 | {contract files/consumers} |
| DATA-01 | {schema、migration、约束和索引} | todo | {owner} | API-01 | {database/modules} |
| BE-01 | {后端 use case/service/adapter} | todo | {owner} | API-01, DATA-01 | {backend modules} |
| FE-01 | {端侧页面、状态和交互} | todo | {owner} | API-01 | {apps/components} |
| TEST-01 | {新增测试基础设施或可复用测试代码；按需} | todo | {owner} | {implementation task} | {test files/tools} |
| DOC-01 | {同步长期产品或技术事实；按需} | todo | {owner} | {implementation task} | {canonical docs} |

## 并行与依赖

- {稳定契约后可以并行的实现流}
- {schema、公共契约或高冲突文件的串行关系}

## 风险

- {开发风险}：影响 {说明}；触发信号 {代码或数据现象}；实现应对 {保护逻辑/兼容方案}；负责人 {owner}

## 决策记录

| 日期 | 决策 | 原因 | 影响任务 |
|---|---|---|---|
| {YYYY-MM-DD} | {会长期影响实现的决定} | {依据} | {TASK-ID} |
```

## 文件拆分

- 默认不拆分。
- 只有 API、backend、frontend 等实现流可以独立交付、独立负责且单文件明显妨碍协作时才拆分。
- 拆分文件仍只保存实现任务；禁止创建 `test-acceptance`、`release`、`verification`、`evidence` 或 `history` 文件。
- 两个以上活跃实现文件确实需要协调时才创建临时总入口；它只保留开发状态、开发 blocker 和活跃实现文件索引，不复制任务或执行记录。最后一个活跃文件归档后立即删除临时总入口；项目长期计划导航保留并更新链接。
