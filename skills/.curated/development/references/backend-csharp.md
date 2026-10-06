# C# Backend Safety

只补充 C#/.NET 特有的失败模式；同时遵守 API、数据和可靠性 reference 中的通用约束。

## Nullable 与异常边界

- 启用并尊重项目 nullable reference types；在 DTO/入口完成校验，不能用 `!` 大面积压掉可能为空的警告。
- 明确区分字段未提供、`null`、`default` 和业务零值；required/nullable DTO、model binding 和序列化行为必须与 API 契约一致。
- 保留 exception chain 和 stack；重新抛出使用 `throw;`，包装时保留 `InnerException`，禁止用 `throw ex;` 重置原始堆栈。
- 只在统一 middleware/filter 边界映射 ProblemDetails 或项目错误结构；已知领域错误不能误报 500，未知异常不能把 stack、SQL 或内部 message 返回给客户端。
- 不要 catch `Exception` 后吞掉、返回成功或重复记录；只有能恢复、补偿、增加有效上下文或在系统边界映射时才捕获。

## Async、取消与 DI 生命周期

- request/job 路径坚持 async all the way；禁止 `.Result`、`.Wait()` 或 `.GetAwaiter().GetResult()` 制造 sync-over-async、线程池饥饿或死锁。
- 把 `CancellationToken` 传给 EF、HTTP、stream、queue 和内部 async 方法；区分客户端取消、超时和业务错误，不能吞掉 `OperationCanceledException` 后继续副作用。
- 除事件处理器外禁止 `async void`；所有 Task 都必须被 await、返回或由受控 background service 持有并观察异常。
- 禁止 singleton 或长生命周期对象捕获 scoped service/`DbContext`；后台任务为每次工作创建并释放 scope。
- `DbContext` 不是线程安全对象，禁止跨并行 Task 共享或并发查询；一个 request/unit-of-work 使用清晰的 scope 和事务边界。
- 对 `IDisposable`/`IAsyncDisposable` 使用 `using`/`await using`；HTTP client 沿用项目 factory/复用方案，不能每个请求临时创建并耗尽 socket。

## EF Core 与查询

- 警惕 `IQueryable` 延迟执行和多次枚举；在明确边界只执行一次，避免日志、映射或校验重复触发相同 SQL。
- 读查询按项目习惯使用 projection、`AsNoTracking`；按基数选择 Include、split query 或显式查询，避免 lazy loading 产生 N+1 或 Include 形成笛卡尔膨胀。
- 部分加载或 detached entity 只更新明确字段；不要把默认值误写回未加载列，重要并发写使用项目已有 concurrency token/row version。
- 处理 `SaveChangesAsync`、commit 和并发冲突异常；执行策略重试必须配合幂等，不能把事务中的外部副作用自动重放。
- EF migration、provider 特性和 SQL 映射使用真实数据库做集成验证；InMemory provider 不能证明事务、约束、NULL 和查询翻译正确。

## 本地开发、Watch 与 Hot Reload

- 本节用于已授权的本地启动或联调；先确认项目标准命令与目标服务。
- 本地联调沿用仓库记录的 dev 命令；没有项目约定时使用 `dotnet watch --project <startup-project> run`。在一次已授权的修改与 smoke 循环中复用同一 watch 进程，不为每次改动重复启动服务；交付时说明访问地址以及进程已保留还是关闭。
- 等待 watch 明确报告 Hot Reload 已应用或进程已重启后再验证。Hot Reload 成功只证明新代码已加载，不能代替受影响 API、页面、后台任务或持久化回读的定向 smoke。
- 修改项目文件、包或项目引用、启动配置、环境变量、生成代码、静态初始化或 singleton 状态时，不依赖旧进程中的 Hot Reload 状态；按 watch 提示重启，最终验证前无法确认状态已刷新则主动重启。
- 不并行运行会写入同一 `bin`/`obj` 的 watch、build、test 或 publish；正式构建前停止对应 watch 或使用项目已有的隔离输出方案，构建后重新启动目标开发产物并复验关键路径。
- 多 worktree 或多 agent 并行联调时，各自使用对应工作树的 watch 进程和无冲突端口；不得复用指向另一工作树输出的进程，也不得为解决端口冲突终止未确认归属的服务。
- 只在容器 bind mount、网络文件系统或确认原生文件监听漏报时启用 `DOTNET_USE_POLLING_FILE_WATCHER=1`，并留意额外 I/O；容器化开发沿用仓库现有 Compose/devcontainer 入口，不临时制造第二套启动路径。

## 验证需求

- 按变更范围选择项目已有 `dotnet format`/analyzer、`dotnet build` 或定向 `dotnet test`；保留 nullable、async 和资源生命周期相关 warning。
- 覆盖 null/default、异常到 status/code 的映射、取消传播、DI scope、`DbContext` 并发保护、查询次数和事务失败。
