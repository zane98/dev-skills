# Go Backend Safety

只补充 Go 特有的失败模式；同时遵守 API、数据和可靠性 reference 中的通用约束。

## Nil 与零值

- 用 constructor 建立必需依赖的非 nil 不变量并在启动时失败；不要让 handler/service 到处猜依赖是否存在。
- 解引用请求字段、关联对象或 repository/外部调用结果前检查契约；避免含义不清的 `(nil, nil)`，not found 必须有统一表达。
- 缺失会影响语义时，对 map、type assertion 和 channel 使用 comma-ok；访问 slice/数组前保证边界成立。
- 警惕 typed-nil：装入 interface/error 的 nil 指针可能不等于 nil；不要把 typed-nil 作为成功或错误结果返回。
- 只在 HTTP/RPC/job 或受控 worker 最外层 recover，记录 stack 和 requestId 后返回通用内部错误；service 内不能依赖 panic/recover 处理正常分支。

## Context、并发与资源

- 把 `context.Context` 作为第一个参数沿 handler → service → repository/外部调用传递；请求链中禁止换成 `context.Background()`/`context.TODO()`、传 nil 或存进长期对象。
- 创建 timeout/cancel context 的一方负责调用 cancel；循环、阻塞 channel、数据库和外部请求必须响应 `ctx.Done()`，并区分取消/超时与业务错误。
- 每个 goroutine 必须有明确所有者、退出条件、取消信号、等待方式和错误去向；请求内副作用禁止无人负责的 fire-and-forget。
- 沿用项目已有 errgroup/worker pool 限制并发；channel 由发送方/所有者关闭，避免 goroutine 泄漏、重复 close 和向已关闭 channel 发送。
- 成功获取 `rows`、HTTP response body、文件、timer/ticker 等资源后立即安排释放；循环内避免 defer 无限累积，并检查影响业务正确性的 close/flush error。
- 受控 worker 的入口是错误边界；框架未兜底时捕获 panic、记录 stack/context 并让任务失败，不能让单个任务静默消失或拖垮进程。

## 数据库映射与事务

- 将 `sql.ErrNoRows` 或 ORM not found 与真实数据库故障分开分类，调用方不得把“没找到”解引用成 panic 或误报 500。
- nullable 列使用 `sql.Null*`、指针或项目统一 nullable 类型，明确 NULL、零值和未提供字段的区别。
- raw SQL 保证列/alias 与 `Scan` 目标顺序和类型一致，检查 `rows.Err()`；ORM 查询检查 tag、preload/join 和部分字段选择。
- 对部分加载的 ORM model 使用显式字段更新，避免 `Save` 把未加载字段的零值写回数据库。
- 沿用项目 transaction helper；直接使用 `database/sql` 时，事务内始终使用 `tx`，延迟 rollback 并检查 commit error，禁止混入全局 `db` 句柄。
- 避免 `:=` 意外遮蔽 `err`，特别是事务、defer 和 handler 分支；每个会影响提交、响应或重试的 error 都必须处理。
- 同一事务内复用已加载实体；只有锁、隔离、数据库生成值或并发正确性要求时才重新查询。

## 错误链

- 需要保留原因时用 `%w` 包装，使用 `errors.Is/As` 分类；不要比较错误字符串，也不要用 `%v` 提前压扁调用方仍需识别的错误。
- 只在有意义的边界增加一次上下文；底层负责返回原因，API/job 边界负责统一记录，避免层层 log-and-return。
- 用项目统一的 typed/sentinel domain error 表达 not found、conflict、validation 和 permission；handler 只做稳定映射。
- 返回前检查 typed-nil error、被吞掉的 error 和错误分支中的错误变量遮蔽，防止“真实失败变成功”或“业务错误变 500”。

## 验证

- 覆盖 nil、typed-nil、零值、NULL、not found、映射失败、领域错误和未知错误的 status/code/message。
- 覆盖 context 取消/超时、资源释放、goroutine 正常退出和错误回传；项目已有泄漏检查工具时沿用。
- 执行项目已有 `go test`、`go vet`/`staticcheck`；并发、锁或共享状态变化时执行适用的 race 检查。
- 数据映射和查询行为使用真实 driver/schema 的集成测试，并按风险断言查询次数，避免只靠 mock 自我感动。
