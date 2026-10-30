# AI 辅助使用说明

## 使用的 AI 工具

- Claude Code（CLI）：代码调试、文档生成

## AI 辅助范围

| 环节 | AI 参与程度 | 说明 |
|---|---|---|
| 架构设计 | 辅助 | 讨论分层结构和 ReAct 循环设计，最终方案由个人确定 |
| 代码编写 | 辅助 | AI 协助编写核心代码，个人审查并调整逻辑 |
| Bug 修复 | 合作 | AI 分析发现 Trace 字段丢失、工具失败无续跑等问题，协作修复 |
| 测试编写 | 辅助 | AI 协助编写测试用例，个人确认覆盖范围 |
| 文档编写 | 辅助 | AI 根据代码分析生成文档框架，个人补充修改 |

## 个人贡献

- 确定项目整体架构和技术选型
- 定义数据模型和业务规则
- 设计测试用例覆盖的场景
- 审查和验证所有 AI 生成的代码
- 确认运行结果符合题目要求

## AI 辅助修复的具体问题

1. **Trace 字段丢失**：`state.py:build_report()` 构建 step_status 时遗漏了 `next_action` 和 `reason` 字段；`agent.py` 中 `next_action` 始终为空字符串，需引入 `prev_rec` 延迟回填机制
2. **工具失败无续跑**：`mock_llm.py` 中 `generate_script` 失败时直接 finish，未体现"保留已成功步骤并续跑"。新增 `_find_search_results()` 从消息历史回溯素材，失败后自动尝试替代素材
3. **步数上限参数未生效**：`run()` 接收 `max_steps` / `max_tool_calls` 参数但未传递给 `check_limits()`，导致测试用的自定义上限无效

## 验证方式

- 所有修改后运行 `python -m pytest tests/ -v`，19 项测试全部通过
- 5 个用例全部跑通，输出归档到 examples/
