# BizBuddy Agent Kernel

BizBuddy 的 B 模块，基于 DSH `0.1.1-rc.2` 提供 Agent 运行时、业务工具、流式事件和会话持久化。

## 目录

- `packages/agent-kernel` 为 Electron 主进程提供稳定的 `AgentKernel` 接口
- `packages/dsh-plugin` 注册 `doc_search`、`ts_list` 和 `ts_query`
- `skills` 保存安环场景的 DSH Skills
- `cordis.yml` 定义 DSH 运行时配置

## 环境

- Node.js 24 或更高版本
- pnpm 11.7.0

## 验证

```bash
pnpm install --frozen-lockfile
pnpm verify
```

`pnpm verify` 会依次执行类型检查、构建和自动测试。集成测试使用 mock 模型和 mock 业务接口，不需要真实模型密钥。

## 运行配置

正式运行时由 Electron 主进程向 DSH 子进程注入以下环境变量。

- `BIZBUDDY_MODEL_API_KEY`
- `BIZBUDDY_MODEL_BASE_URL`
- `BIZBUDDY_MODEL_ID`
- `BIZBUDDY_RAG_BASE_URL`
- `BIZBUDDY_COLLECTOR_BASE_URL`
- `BIZBUDDY_SESSION_DB`
- `BIZBUDDY_SKILLS_DIR`

接口字段和完整调用示例见 [`docs/agent-kernel-interface-protocol.md`](../docs/agent-kernel-interface-protocol.md)，模块设计见 [`docs/bizbuddy-agent-kernel-design.md`](../docs/bizbuddy-agent-kernel-design.md)。
