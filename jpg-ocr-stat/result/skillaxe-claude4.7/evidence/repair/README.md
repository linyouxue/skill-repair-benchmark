# Repair Evidence

`model_calls.tar.xz` 是 53 次实际 client 调用尝试的无损归档，包括全部 wire request、请求审计、响应、pending/completed 标记和基础设施失败记录。归档 SHA-256 为 `7706ad9cea3b823a7ae3d5d4faf6e0a3a2ffd85d5683b94a0db348fae313c789`。解包命令：

```bash
tar -xJf model_calls.tar.xz
```

目录中同时保留了轻量的请求审计、响应和状态 JSON，便于无需展开归档直接核验。每份成功的 `*.request-audit.json` 都记录 `actual_model_delivery_verified=true`、`image_block_count=22`、图片字节数和 SHA-256；归档中的对应 `*.wire-request.json` 保存真正发送给 OpenAI-compatible client 的完整多模态消息。

`history.jsonl` 是 37 轮顺序迭代记录；`coverage.json` 证明 37/37 窗口被消费；`diagnosis.md` 和 `result.json` 是方法输出汇总。API key 和认证 header 未写入任何证据文件。

