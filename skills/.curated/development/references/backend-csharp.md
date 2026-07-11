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

## 验证

- 执行项目已有 `dotnet format`/analyzer、`dotnet build` 和 `dotnet test`；保留 nullable、async 和资源生命周期相关 warning。
- 覆盖 null/default、异常到 status/code 的映射、取消传播、DI scope、`DbContext` 并发保护、查询次数和事务失败。
