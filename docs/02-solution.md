# 方案设计

## 整体架构

采用原生 Python 实现 ReAct（Reasoning + Acting）决策循环，不依赖第三方 Agent 框架。

```
用户输入 → main.py(加载用例) → agent.py(ReAct循环) → mock_llm.py(决策) + tools.py(执行) → state.py(报告) → 输出归档
```

核心分层：

| 层 | 文件 | 职责 |
|---|---|---|
| 入口 | main.py | 加载用例、注入失败、运行 Agent、格式化输出、归档 |
| 循环 | agent.py | ReAct 主循环：上限检查 → 决策 → 校验 → 执行 → 观察回传 |
| 决策 | mock_llm.py | 统一 decide 接口，Mock 与真实 LLM 可切换 |
| 工具 | tools.py | 四个业务工具的 Mock 实现，统一返回 ToolResult |
| 状态 | state.py | AgentState 初始化、上限检查、步骤登记、报告组装 |
| 模型 | models.py | 数据结构定义：ToolResult、StepRecord、AgentState、FinalReport |

## ReAct 调用流程

每轮循环的数据流：

1. `agent.py` 调用 `mock_llm.decide(messages, state)` 获取决策
2. `mock_llm` 根据 messages 中最近一条 tool 结果 + state 当前状态，返回 `{"thought", "action", "args"}`
3. `agent.py` 校验动作合法性，若为 `finish` 则结束循环
4. 否则调用 `_execute_tool(action, state)` → 从 `TOOL_REGISTRY` 取函数执行
5. 构建 `StepRecord`，按 ok/fail 分别写入 `completed_steps` / `failed_steps`
6. 将 action（role=assistant）和 observation（role=tool）追加到 messages
7. 回填上一步 StepRecord 的 `next_action` 字段
8. 回到步骤 1

## 动态决策点

Mock 模型中体现的动态决策逻辑（`mock_llm.py:_decide_mock`）：

### 预算超限 → 自动改选替代方案

- `estimate_cost` 返回 `over_budget=True` 时，Mock 不是按固定分支走，而是观察工具返回的 `over_budget` 字段后决定改选 plan_B
- 如果 plan_B 仍超预算，则返回 incomplete 并报告预算缺口

### 工具失败 → 续跑恢复

- `generate_script` 失败时，Mock 从消息历史中回溯 search_material 的结果（`_find_search_results`），找到未尝试过的素材 ID 重试
- 通过 `state.failed_steps` 追踪已尝试过的素材，避免重复
- 所有素材均失败才报告 failed

### 缺失信息 → 请求补充

- 检测到 budget 或 deadline 为 None 时，直接返回 incomplete 并说明缺失字段

## 技术取舍

| 决策 | 选择 | 理由 |
|---|---|---|
| 框架 | 原生实现 | 题目说明框架不加分，原生实现更清晰地展示 ReAct 循环逻辑 |
| 消息历史 | list[dict] 模拟对话 | 与真实 LLM Chat API 格式一致，切换真实模型时无需改动 agent 循环 |
| 状态管理 | AgentState dataclass | 集中管理，agent.py 只管循环不管状态变更 |
| 失败记录 | completed_steps / failed_steps 分离 | 题目明确要求"失败不记成功"，分离存储天然满足 |
| 幂等保存 | SHA256 幂等键 + 内存草稿库 | 同一请求多次执行只产生一份草稿，满足重复执行验收点 |
| 上限控制 | MAX_STEPS=8, MAX_TOOL_CALLS=12 | 题目要求设执行上限，超限返回明确未完成状态 |
| next_action 回填 | prev_rec 延迟写入 | 执行当前步骤时尚不知道下一步是什么，等下一轮决策后回填到上一步记录 |

## Mock 模型边界声明

- 离线 Mock 模式用预设规则模拟决策，仅验证 ReAct 流程正确性，不证明真实模型决策效果
- 真实模型接口已实现（`mock_llm.py:_decide_real`），通过 `--real` 切换，返回结构与 Mock 一致
- Mock 的决策路径覆盖了题目要求的所有场景：正常、缺信息、超预算、工具失败、重复执行
