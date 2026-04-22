---
name: react-frontend-dev
description: React 前端开发规范 skill，适用于 pnpm + Vite 8.x + Tailwind CSS 的 React 项目，包括用户端与管理后台。Use this skill when building or updating React frontend code, routing, component architecture, TanStack Query data fetching, Zustand state management, BrowserRouter navigation, monorepo shared frontend layers, structured data presentation patterns, or related frontend tech docs. Pair with ui-ux-pro-max whenever UI quality, visual design, interaction quality, accessibility, motion, or overall polish matters.
---

# React Frontend Dev

## Overview

为 React 前端开发提供默认技术选型、组件复用、路由导航、状态管理、monorepo 共享策略和文档同步规则。

## Priority Order

规则优先级按以下顺序决策：

1. 用户明确要求
2. 仓库现有技术栈和约束
3. 本 skill 的默认规则
4. `ui-ux-pro-max` 提供的 UI/UX 质量增强

如果仓库现状与本 skill 不同，优先延续仓库已落地且仍然合理的方案，不要为了对齐 skill 而强行重写整套前端基础设施。

## When to Use

在以下场景使用此 skill：

- 新建或更新 React 前端项目
- 搭建或调整用户端、运营端、管理后台界面
- 设计或重构组件结构、页面路由、请求层、状态层
- 在 monorepo 中抽取共享 API、hooks、组件或查询配置
- 功能、代码结构、框架约束、交互或页面描述变化后同步技术文档

如果任务会影响界面观感、布局、交互、动效、配色、字体、可用性或整体完成度，同时使用 `ui-ux-pro-max`。

## Stack Defaults

- 包管理与脚手架：使用 `pnpm`，优先基于 `Vite 8.x`
- 样式：使用 `Tailwind CSS`
- 数据请求：使用 `TanStack Query`
- 路由：使用基于浏览器 history 的 `BrowserRouter`
- 客户端共享状态：优先考虑 `zustand`
- 用户端表单：优先使用 `react-hook-form + zod`

此 skill 只覆盖前端与用户端开发约束，不负责后台服务、数据库或后端架构设计。

## App-Type Defaults

- 用户端、官网、活动页、内容产品、SaaS 前台：优先使用项目内已有组件，其次 `shadcn/ui`，再考虑自定义组件
- 管理后台、运营平台、内部工具：优先使用项目内已有后台组件，其次 `antd`，表单默认沿用 `antd` 体系
- 多应用仓库：优先抽共享请求层、query 层、基础组件和工具层，而不是各项目复制实现

## Workflow

1. 先识别项目类型：用户端、管理后台、还是 monorepo 多应用场景。
2. 先识别仓库当前包管理器、lockfile 和前端工具链，确认任务所需依赖是否已存在；如果当前 shell 暂时看不到 `node` 或 `pnpm`，先执行下方 `Environment Bootstrap`，再判断工具是否真的缺失。
3. 识别当前功能依赖的真实后端、第三方服务、账号、API key、bucket、短信/支付/IM 配置是否已经到位；只要真实集成所需条件已经满足，默认把真实接口与真实业务状态作为主路径，不再继续沿用页面内 mock 数据、假状态机或演示分支。
4. 优先复用项目内已有组件、样式体系、请求封装和通用 hooks。
5. 再根据项目类型加载对应 reference：
- 用户端：阅读 `references/user-app.md`
- 管理后台：阅读 `references/admin-app.md`
- monorepo：阅读 `references/monorepo.md`
- 需要同步技术文档：阅读 `references/docs-sync.md`
6. 如果任务涉及 UI 质量或视觉设计，联用 `ui-ux-pro-max`。

## Core Rules

### Primary Path First

- 前端实现先保证主交互链路正确、可理解、可测试，线上页面优先追求正常完成任务，而不是先设计一层层 fallback。
- 错误就是错误；没有明确产品要求时，不要用静默降级、假数据、偷偷跳转或模糊提示把真实问题藏起来。
- 只有在明确存在弱网、大型异步区域、第三方依赖不稳定或业务连续性要求时，才设计 fallback、局部隔离或降级展示，并写清触发条件与用户感知。

### Real Integration Beats Mock Once Ready

- 只要任务所需的真实账号、API key、环境变量、回调地址、bucket、第三方应用配置或后端接口已经提供齐全，前端默认接入真实接口与真实状态，不再把 mock 数据、假成功提示、硬编码列表或演示态分支留在主流程。
- mock 仅允许出现在测试、Storybook、纯本地离线开发、临时联调占位或用户明确要求的演示入口中；这类 mock 必须与正式页面、正式路由、正式请求封装和正式构建产物清晰隔离。
- 不要在页面、hooks、store、query adapter、upload helper、payment helper、IM helper 等位置留下“有 key 也继续返回假数据”的影子分支，尤其不要在请求失败、鉴权失败或配置缺失时静默回落到 mock 成功态。
- 如果因为外部依赖尚未开通、白名单未加、回调未配置或服务端 contract 未完成，暂时无法切到真实链路，必须显式说明阻塞点、当前临时 mock 的边界和移除条件，而不是默认把 mock 留在代码里等以后想起来再删。

### Components

- 优先使用成熟组件库或项目内已有组件，再考虑新增自定义组件。
- 禁止直接落浏览器原生 `alert`、`confirm`、`prompt`，应使用项目现有的弹窗、消息、抽屉、Toast、Modal 等反馈组件。
- 组件拆分应以复用性、可测试性和职责单一为目标，避免把页面逻辑全部堆进单个组件。
- 对重复出现的页面骨架、表单片段、列表工具栏、空态、加载态、错误态进行抽取。
- 设计新组件前，先检查仓库是否已有可复用组件、封装或视觉规范。

### Flat-First UI Composition

- 页面结构默认采用扁平化布局，优先组织清晰的内容流、留白节奏和少量关键分区，而不是在页面里一层层包裹容器。
- 页面本身就是设计语言与信息表达，默认不要额外堆长段解释性文字、说明区、提示卡来替页面说话；优先通过标题、字段、布局、默认值、占位、分组和状态本身让界面自解释。
- 只有在存在合规提醒、高风险不可逆操作、首次上手门槛高、系统状态复杂或用户明确需要解释时，才加入必要说明文案；说明要短、贴近动作、贴近控件，不要做大段前置教育。
- 除非信息架构确实需要明显分组，否则不要做 `page shell > section card > inner card > content block` 这类卡片套卡片、边框套边框的层层嵌套。
- 优先用间距、排版层级、浅色块、分栏、分组标题、局部留白和分割线建立信息层次；边框和阴影只作为补充信号，不作为默认视觉骨架。
- 边框应主要用于输入控件、表格分隔、错误警示、选中态或确有必要的内容区隔；页面分区默认优先使用分割线，不要给大多数容器都加一圈边框。
- 阴影应主要用于弹层、浮层、下拉、悬浮操作区或确实需要表达悬浮关系的组件；页面主体区域默认不依赖阴影堆叠层级。
- 使用 `shadcn/ui`、`antd` 或项目现有组件时，如其默认样式带来过重的卡片感、描边感或投影感，应优先做轻量化覆盖，而不是原样堆满整个页面。

### Admin Console Defaults

- 管理后台的 header 默认控制在 `48px` 到 `64px`，优先 `48px` 或 `56px`；不要为了“显气派”把顶部做成大横幅，浪费首屏可用高度。
- 管理后台优先追求信息密度、扫描效率和操作闭环，页面骨架应尽量短平快，不要让大标题区、欢迎语、说明区吃掉主工作区。
- 管理后台页面默认保持扁平，优先使用分割线、分组标题、栅格和留白组织内容，而不是依赖卡片边框、厚描边或容器投影。
- 管理后台默认不使用装饰性阴影；如果组件库自带明显阴影，应优先覆盖为无阴影或极弱阴影，只给弹层、下拉、固定悬浮条等少数需要浮起关系的区域保留。

### Structured Data Presentation

- 对手机号码、价格、货币、百分比、标签、状态、编号、日期时间等标志性信息，优先定义全局统一的展示格式，不要在各页面手写字符串拼接。
- 这类信息优先通过共享 formatter、展示组件或统一映射表实现，例如 `PhoneNumberText`、`PriceText`、`TagGroup`、`StatusBadge` 或项目内等价封装。
- 当信息较长、辨识成本高或需要快速扫读时，应采用分段展示、分组留白、固定精度、统一单位、Badge/Tag、等宽数字或强调层级等方式提升阅读性。
- 同一类信息在列表、卡片、详情页、表单回显、弹窗和导出预览中应保持一致的文案、精度、分隔符、颜色语义、空值态和交互反馈。
- 如果仓库已有全局格式化工具、字典映射或展示组件，应优先复用；如果没有，应沉淀到共享层，而不是散落在单个页面里重复实现。

### Forms

- 用户端表单默认采用 `react-hook-form + zod`，统一表单状态、校验规则和提交流程。
- 管理后台表单不强制 `react-hook-form`，默认沿用 `antd` 的表单体系和项目现有后台封装。
- 表单校验、错误提示、禁用态、提交中状态和成功反馈要成套出现，不要只做字段渲染。
- 复杂表单的 schema、默认值、提交转换逻辑应有稳定落点，不要散在页面 JSX 中。

### Data and State

- 服务端数据统一走 `TanStack Query`，不要手写零散的加载、缓存、重试和失效逻辑。
- 跨组件共享状态、筛选条件、草稿态、会话级 UI 状态优先考虑 `zustand`。
- 不要用成对 `useState` 到处传值，也不要直接把状态管理退化成零散 `localStorage` 读写。
- `localStorage` 仅作为持久化介质，不应替代状态层；如确有必要，应由 `zustand` 或统一封装负责持久化。
- 页面级临时 UI 状态可以保留在组件内，但一旦出现跨组件同步、持久化、共享筛选或复杂流程状态，就应评估 `zustand`。

### Routing and Navigation

- 使用浏览器路由，不采用 hash 路由作为默认方案。
- 返回按钮语义必须是“后退”，优先使用 `navigate(-1)` 或等价 history back 行为。
- 不要把“返回”实现成跳去某个预设页面，更不要把它实现成继续向前导航。
- 新页面、弹层、详情页、编辑页都要检查返回路径是否符合用户预期。
- 用户端列表页的筛选、分页、排序默认同步到 `search params`，以保证返回、刷新和分享链接行为稳定。
- 管理后台不强制 URL 状态同步，按现有后台模式和复杂度决定是否接入。

### Environment Bootstrap and Tooling

- 非交互 shell、受控执行器或桌面代理环境经常不会加载 `~/.zshrc`；不要因为一次 `command -v node` / `command -v pnpm` 失败，就直接断言本机未安装。
- 在声明 `node`、`pnpm`、`npm`、`npx` 缺失之前，先在当前 shell 依次尝试常见初始化，再重新检查命令可见性。
- macOS + Homebrew：如果存在 `/opt/homebrew/bin/brew`，先执行 `eval "$(/opt/homebrew/bin/brew shellenv)"`，避免 Homebrew PATH 未注入。
- `nvm` 环境：如果存在 `$HOME/.nvm/nvm.sh`，执行 `export NVM_DIR="$HOME/.nvm"` 与 `. "$NVM_DIR/nvm.sh"`；如果 `nvm` 可用，再执行 `nvm use --silent default`，让默认 Node 版本进入 PATH。
- `pnpm` 独立安装：如果存在 `$HOME/Library/pnpm`，执行 `export PNPM_HOME="$HOME/Library/pnpm"`，并把它补到 PATH 前部后再重试 `pnpm -v`。
- `corepack` 备用入口：如果 `node` 已可用但 `pnpm` 仍不可见，先尝试 `corepack pnpm --version`；若可用，可临时使用 `corepack pnpm <command>` 完成当前任务，而不是直接说缺少 `pnpm`。
- 只有在完成上述自举并复检后仍失败，才能对用户说工具缺失；说明时要明确写出已尝试过哪些自举步骤。

- 在执行格式化、lint、类型检查、构建或脚手架命令前，先检查仓库是否已安装所需依赖，例如 `prettier`、`eslint`、`typescript` 及相关插件、解析器。
- 如果任务依赖这些工具而仓库缺失，应自行安装到项目内，优先沿用仓库现有包管理器；默认使用 `pnpm`，但若仓库已有其他 lockfile 或明确约束，则以仓库现状为准。
- 新增这类工具依赖时，默认写入 `devDependencies`，并同步更新对应 lockfile；不要用全局安装替代项目依赖。
- 安装前应尽量选择与仓库当前 React、Vite、ESLint、Tailwind 生态兼容的版本，避免为了跑通单次命令引入冲突版本。
- 如果仓库明确禁止新增依赖、当前环境离线、或安装会破坏现有约束，需要明确说明原因，并给出不破坏仓库约束的替代执行方案；否则不要把安装工作留给用户。

### Error Handling

- 统一错误提示风格，不要让同一项目同时出现多套失败反馈方式。
- 页面和关键区块都应有明确的加载态、空态和错误态；是否提供重试入口按场景决定。
- 请求失败后应根据场景提供可恢复路径，例如重试、返回、重新筛选或联系支持；不要机械地给每个失败都套同一种 fallback。
- 关键页面和高风险区域可放置 `Error Boundary` 做局部隔离，但它的作用是阻止整页崩溃并暴露错误，不是掩盖根因。
- 异步提交失败时，优先使用项目统一的消息组件、表单错误提示或结果态组件，而不是临时 `console.error` 后无反馈。

### Reuse and Structure

- 合理拆分页面层、业务组件层、基础组件层、hooks 层、api 层。
- 将请求定义、query keys、数据转换和通用 UI 逻辑放在稳定的共享边界，减少页面直接耦合。
- 新增能力时先查找已有实现，避免重复造轮子和并行维护两套组件。
- 导入别名默认使用 `@/shared`、`@/features`，避免深层相对路径在项目中蔓延。

## Avoid

- 不要在页面里直接散落请求、缓存处理、错误提示和数据转换逻辑
- 不要把“为了快”当作长期结构设计，留下重复实现和不可复用页面
- 不要把原生浏览器交互当正式产品交互方案
- 不要把返回按钮实现成跳首页、跳列表页或继续向前导航
- 不要在 monorepo 中复制相同 API 封装、query 封装和基础组件
- 不要在功能已变化后遗漏对应技术文档更新
- 不要把页面做成层层嵌套的卡片森林，尤其避免大卡片里再套多层小卡片
- 不要用满屏边框、厚阴影或重复描边来硬造层级，优先回到留白、排版和色块关系
- 不要默认在页面顶部堆欢迎语、使用指南、解释性段落，尤其不要让后台页面像 PPT 封面
- 不要把后台 header 做得又高又空，吞掉首屏工作区
- 不要在真实账号和 key 已到位后，继续让正式页面依赖 mock 数据、假状态流或伪造提交结果
- 不要把“请求失败时先给一份假数据顶上”当成默认前端韧性方案

## Project-Type References

- 用户端规则：`references/user-app.md`
- 管理后台规则：`references/admin-app.md`
- monorepo 共享策略：`references/monorepo.md`
- 技术文档同步规则：`references/docs-sync.md`

## Output Expectations

在执行前端任务时，默认产出应符合以下标准：

- 技术选型与本 skill 一致，除非仓库现状或用户明确要求不同
- 新增代码优先接入现有组件体系、请求层和状态层
- 路由返回行为符合 history back 语义
- 可复用逻辑被抽取到合适层级，而不是散落在页面内部
- 页面视觉层级保持扁平、克制，避免无意义的容器嵌套、重复边框和装饰性阴影
- 页面优先靠结构自解释，而不是额外说明文案兜底；后台 header 和页面骨架保持紧凑
- 功能、代码或框架变化时同步相关技术文档

## Delivery Checklist

交付前至少检查以下项目：

- 是否优先复用了已有组件或成熟组件库
- 表单是否符合用户端 `react-hook-form + zod` 或后台 `antd` 默认方案
- 服务端数据是否接入 `TanStack Query`
- 共享状态是否评估了 `zustand`
- 返回按钮是否为 history back 语义
- 用户端列表页状态是否正确同步到 `search params`
- 页面是否具备加载态、空态、错误态和成功反馈
- 是否按场景接入统一错误提示、恢复操作和必要的 `Error Boundary`
- 手机号、价格、tag、状态等标志性信息是否采用统一格式、组件或分段展示
- 页面结构是否避免了卡片套卡片、边框套边框，并优先通过留白和排版建立层次
- 是否避免了无必要的解释性文字；如确需说明，是否足够短并紧贴动作
- 管理后台 header 是否控制在 `48px` 到 `64px`，且页面是否优先使用分割线而不是容器边框/阴影
- monorepo 变更是否提取了可共享层
- 执行所需的 `prettier`、`eslint`、`typescript` 等工具依赖若缺失，是否已按仓库包管理器补齐并更新 lockfile
- 如果真实账号、key 和接口已就绪，正式页面、正式路由、正式 hooks 和正式 store 是否已经切到真实链路
- 是否清理了主流程中的 mock 数据、假成功态、影子 adapter、演示态 fallback 和仅为“先跑起来”留下的临时分支
- 技术文档是否已同步更新
