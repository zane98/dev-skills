# Rust Backend Safety

只补充 Rust 特有的失败模式；同时遵守 API、数据和可靠性 reference 中的通用约束。

## 错误、空值与边界

- 用 `Result` 和可分类的领域错误表达可恢复失败，并保留 error source；沿用项目已有 `thiserror`、`anyhow` 或等价模式，不另造错误体系。
- 领域/service 边界优先返回稳定 typed error；动态错误只留在应用装配或内部边界，HTTP/job 边界再统一映射和记录完整 source chain。
- 请求、数据库、外部依赖和消息数据不能靠 `unwrap`/`expect`；只允许在测试、启动期不变量或已有证明充分的内部不变量使用并说明原因。
- `Option` 必须明确表示“可缺失”还是“数据库 NULL”；需要区分字段未提供与显式 null 时，使用项目已有 wrapper/枚举或嵌套表达，不能把两者压成同一语义。
- panic 不是业务错误；不要用 `catch_unwind` 维持正常控制流。使用 `unsafe` 时限制在最小边界，写清 safety invariant 并增加针对性测试。

## Async、并发与生命周期

- async runtime 内禁止直接执行阻塞 I/O、长 CPU 计算或同步 sleep；使用项目异步 API，确需 blocking 时放入有界 blocking pool/worker。
- 不要让同步 `Mutex/RwLock` guard 或与当前异步操作无关的可变借用跨 `.await`；先提取必要状态并释放 guard。transaction/connection 只在连续数据库操作期间持有，不跨外部调用或其他无关 await。
- 每个 spawned task 必须有所有者、取消条件、Join/错误处理和关闭路径；请求内副作用禁止 detached spawn，不能丢弃 `JoinHandle` 中的 panic/error。
- 使用 `select`/取消时确认 future 是否 cancellation-safe；消息 ack、事务提交和外部副作用不能因取消停在含义不明的半完成状态。
- `Arc` 只表达共享所有权，不默认等于线程安全；避免用 `Arc<Mutex<_>>` 把边界不清的共享可变状态包装成“能编译就行”。

## 数据、序列化与资源

- serde DTO 与数据库 model 分离；明确 rename、default、unknown field/enum 和新增字段的兼容行为，不能把内部 model 直接当公共契约。
- 数据库行映射检查列名、类型、NULL 和 enum；沿用项目 SQLx/Diesel/ORM 能力，并用真实数据库验证编译期检查覆盖不到的动态 SQL 和迁移状态。
- 事务使用同一 connection/executor 并保持短小；外部调用、阻塞任务和无关 await 不放进事务，commit/error 必须被处理。
- 流式响应、数据库 cursor 和 request body 要有大小、并发和超时边界；RAII 会释放资源，但不能替代对 task、stream 和连接生命周期的主动关闭。
- 外部整数和长度转换使用 checked/`TryFrom` 路径，避免 `as` 截断、符号转换和无界分配。

## 验证

- 执行项目已有 `cargo fmt --check`、`cargo check`、`cargo clippy` 和 `cargo test`；使用与部署一致的 feature/target，不盲跑互斥的 all-features。
- 覆盖 `Option`/NULL、serde 兼容、错误 source/API 映射、task 取消/Join、阻塞隔离和事务回滚。
- 涉及并发、unsafe 或复杂 async 时沿用项目已有 loom、Miri、sanitizer 或集成测试；没有对应工具时明确未验证风险。
