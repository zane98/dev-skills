# React

用于基础框架或现有项目已选择 React 的 Web 任务。

## 栈内边界

- 从 `package.json`、Vite/Next 配置、路由入口、Provider 和主题入口识别真实构建、渲染、组件、路由、数据和状态方案，并沿用现状。
- 只有选型任务才比较方案：普通 SPA 可使用 React + Vite + TypeScript；明确需要 SSR、SEO、服务端组件、服务端 action 或 edge 能力时再选择 Next.js 等服务端框架。
- shadcn/ui、Ant Design 或其他组件系统沿用项目选择及封装，不并行引入第二套基础组件、表单或反馈体系。

## React 适配

- 使用项目实际路由器的类型、loader 和 search params 能力；可分享筛选、分页和 tab 状态进入 URL，默认值修正通常使用 `replace`。
- React Query、SWR、Apollo 或其他数据层的缓存标识必须包含真正影响结果的路由和业务参数；预取只覆盖明确下一步路径。
- 不用 `useEffect` 镜像 props、拼第二份派生状态或重写请求生命周期；副作用只同步组件外部系统。
- 本地交互先用组件状态；状态转换复杂时用 reducer，真正跨页面才进入项目 store。
- Next.js 项目明确 server/client component 边界、缓存和 hydration；秘密、服务端权限判断和仅服务端依赖不得进入客户端包。

## 组件与验证

- shadcn/ui 项目优先组合 primitives 和 token；Ant Design 项目复用 Form、Table、Modal、Drawer 与反馈能力。
- 共享组件覆盖项目实际需要的 loading、empty、error、disabled 和 permission 状态，不把页面请求与路由细节塞进基础组件。
- 验证刷新、前进/返回、深链、URL 状态恢复；SSR 项目额外检查 hydration、服务端/客户端输出和客户端包边界。
