# Python Backend Safety

只补充 Python 特有的失败模式；同时遵守 API、数据和可靠性 reference 中的通用约束。

## 类型、空值与输入

- type hint 不提供运行时校验；所有外部输入必须通过项目现有 schema/serializer/validator，在进入 service 前得到可信类型和范围。
- 明确区分字段 missing、`None`、`False`、`0`、空字符串和空集合；需要表达“未提供”时使用项目 schema 能识别的 sentinel/fields-set，不能只写 `if not value`。
- dataclass、函数参数和 model 字段禁止共享可变默认值；使用 `default_factory` 或每次创建新对象。
- ORM model、输入 DTO 和输出 schema 分离；序列化不能触发隐式数据库查询，也不能把内部字段或 lazy relation 偷偷暴露给客户端。
- 禁止对不可信数据使用 `eval`、`exec`、pickle 或不安全反序列化；沿用项目安全 loader 和允许列表。

## Async、并发与资源

- async endpoint/job 中禁止直接调用同步数据库、HTTP、文件 I/O、sleep 或长 CPU 计算；改用 async client，或把不可替换的阻塞工作放入有界 thread/process worker。
- 每个 `create_task` 都必须有所有者、await/取消、异常收集和关闭路径；优先沿用项目 TaskGroup/worker，禁止请求结束后无人负责的 orphan task。
- 传播 timeout/cancellation；不要把 `CancelledError` 或超时吞成普通成功/500 后继续写入，事务和外部副作用必须停在可恢复边界。
- session/connection 按 request/job unit-of-work 创建；SQLAlchemy `Session/AsyncSession` 不能跨并发 task 共享。
- 使用 `with`/`async with` 释放 session、response、stream、file 和 lock；HTTP client 按项目生命周期复用，不能每次请求创建新连接池。
- GIL 不能保证复合操作线程安全，也不能让 CPU 任务并行；多进程 worker 之间更不能把内存对象当共享事实来源。

## 异常、事务与 ORM

- 包装异常使用 `raise ... from err` 保留 cause，原样重抛使用 bare `raise`；不要用 `raise err` 改写 traceback，也不要比较异常字符串。
- 不要用宽泛 `except Exception` 吞错、返回成功或统一改成 500；只在能恢复、补偿、增加有效上下文或边界映射时捕获。
- 使用项目 transaction/unit-of-work context 管理 commit/rollback；区分 flush 与 commit，任何异常路径都不能留下含义不明的半完成状态。
- 禁止在循环、property、schema 序列化或 lazy relation 中隐藏 N+1；使用项目 ORM 的 eager/batch loading，并对关键 endpoint 断言查询次数。
- 映射敏感查询使用真实 driver/schema 验证 NULL、Decimal、datetime/timezone、enum 和数据库异常，不能只靠与生产不同的 SQLite/mock 替代生产数据库语义。

## 验证需求

- 按变更范围选择项目已有 formatter/linter、`mypy`/`pyright` 或定向 `pytest`；类型检查通过不等于运行时输入安全。
- 覆盖 missing/`None`/零值、异常 cause/API 映射、取消/超时、task 退出、session rollback、资源释放和查询次数。
- async、线程或多进程改动增加对应并发测试；测试必须有 timeout，避免泄漏任务把测试套件一起拖进沼泽。
