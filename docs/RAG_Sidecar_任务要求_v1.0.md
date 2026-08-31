# RAG Sidecar 任务要求

> 本表为 RAG Sidecar 的项目范围/任务要求摘要，与《RAG Sidecar API 接口协议 v1.0》配套。以下内容已按协议修正。

| 项 | 内容 |
| --- | --- |
| 任务 | 从现有 backend/ 裁剪：去 Postgres/多用户鉴权，元数据改 SQLite，向量库换嵌入式 LanceDB；文档解析（PDF/Word/Excel/图片）、切片、BGE Embedding、rerank；索引管理 API（索引状态查询、异步重建、异步删除）；PyInstaller 打包（one-file/one-folder 均可，模型大时推荐 one-folder） |
| 交付物 | sidecar 可执行文件 + HTTP API（仅 loopback） |
| 依赖 | 无（可最先启动）；Backend / Electron / Frontend 都消费它的 API |
| 验收 | 上传文档 → 状态流转（解析中→已入知识库）；提问能命中引用；删除文档后检索不到 |
