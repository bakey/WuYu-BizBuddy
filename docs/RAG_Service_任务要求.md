# RAG Service 任务要求

> 本表为 RAG Service 的项目范围/任务要求摘要，与《RAG Service API 接口协议》配套。以下内容已按协议修正。

| 项 | 内容 |
| --- | --- |
| 任务 | 从现有 backend/ 裁剪：多用户鉴权与用户体系上移到 service 层（RAG Service 无鉴权，仅服务同 pod 的 service，上传人 uploader 归属是刚需）；数据存储统一改用 PostgreSQL（元数据 + 向量，pgvector）；文档解析（PDF/Word/Excel/图片）、切片、BGE Embedding、rerank；索引管理 API（索引状态查询、异步重建、异步删除）；以容器镜像交付（与 service、PostgreSQL 同 pod） |
| 交付物 | RAG Service 容器镜像 + HTTP API（仅同 pod localhost，由 service 统一代理调用） |
| 依赖 | 与 service、PostgreSQL 同 pod 部署；service 消费其 API，桌面端/前端经 service 转发 |
| 验收 | 上传文档 → 状态流转（解析中→已入知识库）；提问能命中引用；删除文档后检索不到 |
