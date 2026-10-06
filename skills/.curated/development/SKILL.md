---
name: development
description: 所有软件开发与开发文档变更的统一入口。用于实现功能、修 bug、重构、前端页面与交互、后端 API 与服务、跨前后端契约联调、数据库、配置或架构调整，以及产品与技术文档同步；根据改动按需读取前端、后端、跨层契约和语言 reference，复杂或明确要求计划的任务叠加 development-plan。要求沿用项目约定、控制范围、保持兼容并按风险验证。
---

# Development

统一编排前端、后端和跨层开发；领域细节按需读取 reference，用户指令和项目 `AGENTS.md` 优先。

## 核心约束

- 改动贴近请求，不扩展非目标，不顺手清理无关问题。
- 修改前识别并保留用户已有改动，不覆盖、不回退任务外内容。
- **DRY**：优先复用标准库、成熟库和项目现有组件/service/工具；只有语义一致、真实重复或项目已有模式时才抽象，不为减少代码强行合并不同业务。
- **KISS**：在满足正确性、安全和可维护性边界的前提下，选择最简单、清晰、易修改的方案；新增复杂度必须对应可说明的真实问题。
- 手写、可拆分源码接近或超过 800 行时触发职责审查；新增文件原则上不越线，已超限文件的小修不强制先重构，新增职责或大改且能控制风险时再拆分。生成文件、lockfile、固定格式 schema/fixture 等例外，无法合理拆分时说明原因。
- 工具函数必须归属明确模块，不创建无主的通用垃圾桶。
- 先识别本次涉及的前端、后端、数据、契约和运行边界，只读取匹配 reference，不为完整感加载无关领域。
- 字段或业务事实跨越客户端、API、服务和存储，或需要判断真实链路是否完成时，读取 `references/cross-layer-contract.md`，不能用单层实现推断整条链路完成。
- 复杂、跨层或架构任务使用 `$development-plan` 进行分阶段处理和进度跟踪；只有用户明确只要计划时才停止在计划阶段。
- 修改公共契约、持久化数据、配置格式、模块边界、技术栈或运行拓扑时默认保持向后兼容；确需破坏性变更时，明确调用方、迁移、发布、回滚和验收路径。

## 流程

1. 盘点：读 `AGENTS.md`、README、相关源码/测试和项目约定；可能改变产品定义或关键方案时再读对应产品文档。
2. 定界：明确目标、非目标、用户可见行为和验收条件；简单任务在心中完成，不为形式输出长计划。
3. 路由：判断涉及的端、技术栈、契约、数据和运行风险，读取下方匹配 reference。
4. 排序：先稳定业务事实、数据来源和跨层契约，再实现事实生产方与高风险侧，随后实现消费方；前端原型、已有 API 接入或单层任务按真实依赖跳过不适用步骤。
5. 实现：修改真实功能代码；修 bug 时先取得可复现现象或失败证据，再定位根因，不只压住表面症状。
6. 联调：跨层任务分别验证写入与读取链路、契约、权限、正常/空/错/加载态、状态恢复和关键失败路径；单层任务只覆盖受影响边界。
7. 同步：产品事实、已记录方案或长期架构约束变化时按文档协议更新，不把文档写成代码修改日志。
8. 验证与收尾：检查 diff 并执行最小充分检查；说明代码、文档、验证结果和未覆盖风险。

## Reference 选择

只读取当前任务命中的文件；一个任务可以组合多个 reference。

| 变化 | Reference |
| --- | --- |
| 产品事实、产品文档、Code Map、架构约束或文档协议 | `references/product-code-sync.md` |
| 跨前后端字段、mock 转真实接口、提交后查询回显、多消费者链路或完成度判断 | `references/cross-layer-contract.md`，并组合命中的前端、API 和数据 reference |
| 前端页面、组件、请求、路由、状态、表单、权限、性能或可访问性 | `references/frontend-core.md` |
| 视觉实现、Figma 映射或 design token | `references/frontend-design-token.md` |
| UI 质感受质疑、参考学习或视觉改进 | [审美校准与验收](references/frontend-ui-quality.md)；与 token 合规分别判断，先验证一个真实页面 |
| React Web | `references/frontend-react.md` |
| 微信小程序（无论原生、Taro 或 uni-app）的任何改动 | `references/frontend-wechat-miniprogram.md`，并组合所用框架 reference |
| Taro 小程序 | `references/frontend-taro-miniprogram.md` |
| uni-app 小程序 | `references/frontend-uniapp-miniprogram.md` |
| 后端模块边界、分层、服务拆分或核心业务流程 | `references/backend-architecture.md` |
| API、错误码、分页、幂等或版本兼容 | `references/backend-api-contract.md` |
| 表、模型、migration、索引、事务、金额、时间或查询性能 | `references/backend-data-modeling.md` |
| 缓存、队列、后台任务、重试或补偿 | `references/backend-cache-and-queue.md` |
| 登录、鉴权、权限、租户、输入、密钥、限流、CSRF/CORS 或 SSRF | `references/backend-auth-security.md` |
| 日志、错误、trace、metrics、外部依赖、容量、背压、健康检查、降级或发布回滚 | `references/backend-reliability.md` |
| Go 后端 | `references/backend-golang.md` |
| Rust 后端 | `references/backend-rust.md` |
| C#/.NET 后端 | `references/backend-csharp.md` |
| Python 后端 | `references/backend-python.md` |

## 验证与完成

- 按出错概率、影响范围、可逆性和发现难度选择能直接覆盖变化的最小检查集合。
- 纯文案/样式检查 diff 并按需查看页面；局部行为、配置或依赖变化选择相关 lint、typecheck、build、定向测试、smoke 或依赖检查。
- 契约、状态流转、共享逻辑和数据语义执行定向测试并检查关键路径。
- 订单、支付、金额、权限、认证、迁移和不可逆操作覆盖正常、边界、失败路径，并检查相关幂等、一致性和回滚。
- 除项目强制要求、高风险或影响面证据外，不跑全量测试；代码和环境未变时不重复验证。
- 无关既有失败只记录；无法验证或验收条件未满足时，说明缺口和剩余风险，不声称任务完成。
