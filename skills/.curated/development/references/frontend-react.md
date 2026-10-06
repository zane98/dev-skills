# React

用于基础框架或现有项目已选择 React 的 Web 任务。

## 栈内边界

- 从 `package.json`、Vite/Next 配置、路由入口、Provider 和主题入口识别真实构建、渲染、组件、路由、数据和状态方案，并沿用现状。
- 只有选型任务才比较方案：普通 SPA 可使用 React + Vite + TypeScript；明确需要 SSR、SEO、服务端组件、服务端 action 或 edge 能力时再选择 Next.js 等服务端框架。
- shadcn/ui、Ant Design 或其他组件系统沿用项目选择及封装，不并行引入第二套基础组件、表单或反馈体系。

## React 适配

- 使用项目实际路由器的类型、loader 和 search params 能力；可分享筛选、分页和 tab 状态进入 URL，默认值修正通常使用 `replace`。
- 请求遵循 [前端核心](frontend-core.md) 的去重与保鲜要求；预取只覆盖明确下一步路径。
- 不用 `useEffect` 镜像 props、拼第二份派生状态或重写请求生命周期；副作用只同步组件外部系统。
- 本地交互先用组件状态；状态转换复杂时用 reducer，真正跨页面才进入项目 store。
- Next.js 项目明确 server/client component 边界、缓存和 hydration；秘密、服务端权限判断和仅服务端依赖不得进入客户端包。

## 请求机制

- 已有 React Query（TanStack Query）、SWR、Apollo 或框架 loader/cache 时沿用其统一机制；React 客户端缺少共享服务端状态管理且确有上述需求时，优先评估 TanStack Query。选库须能解决当前生命周期问题，安装库本身不算完成去重。
- TanStack Query 的浏览器端 `QueryClient` 在应用/会话边界保持稳定，不随页面挂载或 render 重建；同一业务查询复用 key、query function 与时效配置，loader/预取和组件订阅进入同一缓存。用 `enabled` 等实际版本支持的机制等待依赖就绪，不在 query 自动执行之外又通过挂载 effect 或参数监听调用 `refetch`。
- 按资源时效设置 `staleTime`；默认立即 stale 仍可在挂载、窗口聚焦或重连时重新获取，进行中的请求去重不能阻止完成后的这些请求。`gcTime`（旧版 `cacheTime`）决定无人订阅缓存的保留时间，不是保鲜期。检查 `refetchOnMount`、`refetchOnWindowFocus`、`refetchOnReconnect`、轮询与重试的组合，不为减少计数统一设为永久新鲜或全部关闭；合法刷新需保持有效。
- React StrictMode 开发期可能额外执行 effect 的 setup/cleanup；保留检查并核对请求来源、取消与重挂载行为，不靠移除 StrictMode、`useRef` 一次性闸门或忽略取消信号凑出“一次”。区分取消后的重发与重复成功读取，同时验证快速切换时旧结果不会覆盖新状态。
- SSR 按服务端请求隔离缓存；通过框架数据交接或 dehydration/hydration 让客户端复用首屏数据，并按时效判断是否刷新，避免服务端预取后客户端盲目再拉。不要把浏览器端稳定实例规则误用为跨用户的服务端全局单例。

具体 API 按项目安装版本核对：[默认行为](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults)、[取消请求](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation)、[SSR 与 hydration](https://tanstack.com/query/latest/docs/framework/react/guides/ssr)、[React effect 生命周期](https://react.dev/learn/synchronizing-with-effects)。

## 组件与验证需求

- shadcn/ui 项目优先组合 primitives 和 token；Ant Design 项目复用 Form、Table、Modal、Drawer 与反馈能力。
- Ant Design 项目的日期和日期区间字段默认使用 `DatePicker` / `RangePicker`；`Input type="date"` 即使从 `antd` 导入，仍只是套用 Input 外观的浏览器原生日期控件，不能据此宣称已使用 Ant Design 日期组件。只有产品或宿主平台明确要求原生日期控件时才保留，并说明该约束。
- Ant Design 日期组件使用 Dayjs 等 UI 值，而 API 使用 `YYYY-MM-DD` 等序列化字符串时，在表单组件或 API 边界集中转换，不能让 UI 库值泄漏到共享 DTO。实现阶段搜索受影响应用中的原生日期输入；再覆盖新增默认值、编辑回显、选择、清空、提交值、locale 和表单宽度，看到 `antd` import 不算完成证据。
- Ant Design 的表格密度可能影响内置分页：例如 [5.27.6 的实现](https://github.com/ant-design/ant-design/blob/5.27.6/components/table/InternalTable.tsx)会在 `Table size="middle"` 且未设置分页 size 时使用 `small`。页面要求常规分页密度时，按项目安装版本的类型与实现显式配置（5.x 为 `pagination.size: "default"`）；不要跨版本套用名称。同时检查分页 class、点击盒尺寸和页码间距，不能只改全局 token 后凭源码判断视觉已统一。
- 共享组件覆盖项目实际需要的 loading、empty、error、disabled 和 permission 状态，不把页面请求与路由细节塞进基础组件。
- 验证刷新、前进/返回、深链、URL 状态恢复；SSR 项目额外检查 hydration、服务端/客户端输出和客户端包边界。
