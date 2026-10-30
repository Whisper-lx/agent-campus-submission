# 测试与评估

## 测试概览

```bash
python -m pytest tests/ -v
# 20 passed
```

三组测试文件：

| 文件 | 测试数 | 覆盖范围 |
|---|---|---|
| test_tools.py | 7 | 工具层：估算、幂等保存、失败注入、缺参数 |
| test_agent_loop.py | 7 | ReAct 循环：正常路径、超预算重规划、缺信息、工具失败恢复、全部重试耗尽、上限、Trace 字段 |
| test_acceptance.py | 6 | 验收点：正常、缺信息、工具失败、预算超限（无可行方案）、重复执行、失败续跑恢复 |

## 验收点测试结果

### 1. 正常完成

- 测试：`test_accept_normal`、`test_normal_success`
- 输入：topic="产品发布短视频", budget=10, deadline="2026-11-10"
- 预期：status=success，方案已保存，total_cost=8
- 实际：通过。Agent 执行 search → generate → estimate(plan_A 超预算) → estimate(plan_B 可行) → save → finish
- 运行记录：[examples/traces/case_normal.jsonl](../examples/traces/case_normal.jsonl)
- 输出：[examples/outputs/case_normal_output.md](../examples/outputs/case_normal_output.md)

### 2. 缺预算或截止时间

- 测试：`test_accept_missing_deadline`、`test_missing_budget_incomplete`
- 输入：budget=null, deadline=null
- 预期：status=incomplete，原因包含"预算"或"截止时间"
- 实际：通过。Mock 检测到缺失字段后直接返回 incomplete，不执行任何工具
- 运行记录：[examples/traces/case_missing_info.jsonl](../examples/traces/case_missing_info.jsonl)
- 输出：[examples/outputs/case_missing_info_output.md](../examples/outputs/case_missing_info_output.md)

### 3. 工具失败

- 测试：`test_accept_tool_failure`、`test_tool_failure_not_counted_success`
- 输入：正常输入 + 注入 save_plan 失败
- 预期：失败步骤 ok=False，不混入成功步骤；前序成功步骤结果保留
- 实际：通过。前 4 步成功结果保留，第 5 步 save_plan ok=False，status=failed
- 运行记录：[examples/traces/case_tool_failure.jsonl](../examples/traces/case_tool_failure.jsonl)
- 输出：[examples/outputs/case_tool_failure_output.md](../examples/outputs/case_tool_failure_output.md)

### 4. 预算超限

- 测试：`test_accept_budget_over`
- 输入：budget=5（plan_A 估算 12，plan_B 估算 8，均超预算）
- 预期：status=incomplete，返回缺口信息
- 实际：通过。Agent 先估算 plan_A 发现超预算，改选 plan_B 重新估算仍超预算，返回 `"预算 5 不足，最低方案 plan_B 估算 8，缺口 3"`
- 运行记录：[examples/traces/case_buget_over.jsonl](../examples/traces/case_buget_over.jsonl)
- 输出：[examples/outputs/case_buget_over_output.md](../examples/outputs/case_buget_over_output.md)

### 5. 重复执行

- 测试：`test_accept_duplicate_save_one_draft`
- 输入：相同请求执行 2 次
- 预期：两次运行产生相同的 draft_id，草稿不重复创建
- 实际：通过。第二次 save_plan 返回"已存在草稿 draft_001，未重复创建"
- 运行记录：[examples/traces/case_duplicate.jsonl](../examples/traces/case_duplicate.jsonl)
- 输出：[examples/outputs/case_duplicate_output.md](../examples/outputs/case_duplicate_output.md)

### 6. 失败步骤续跑（加分项）

- 测试：`test_accept_tool_recovery`
- 输入：正常输入 + 注入 generate_script 失败 1 次
- 预期：M01 生成失败后改用 M02 重试成功，失败步骤记为 ok=False，整体 status=success
- 实际：通过。search(成功) → generate_script M01(失败) → generate_script M02(成功) → estimate(plan_B 可行) → save → finish
- 运行记录：[examples/traces/case_tool_recovery.jsonl](../examples/traces/case_tool_recovery.jsonl)
- 输出：[examples/outputs/case_tool_recovery_output.md](../examples/outputs/case_tool_recovery_output.md)

## 其他测试

| 测试 | 验证内容 | 结果 |
|---|---|---|
| test_budget_over_replans_to_plan_b | budget=10 时 plan_A 超预算改选 plan_B 成功 | 通过 |
| test_step_limit_returns_incomplete | 步数上限（max_steps=2）触发 incomplete | 通过 |
| test_tool_failure_all_retry_exhausted | 所有素材均生成失败时返回 failed | 通过 |
| test_trace_has_next_action_and_reason | Trace 中每步都包含 next_action 和 reason 字段 | 通过 |
| test_estimate_cost_* | 超预算/在预算内/缺预算三种情况 | 通过 |
| test_save_plan_idempotent | 幂等键相同时不重复创建草稿 | 通过 |
| test_generate_script_missing_material | 素材不存在时返回 ok=False | 通过 |

## 用例与验收点覆盖矩阵

| 用例 | 正常完成 | 缺信息 | 工具失败 | 预算超限 | 重复执行 | 续跑恢复 |
|---|---|---|---|---|---|---|
| case_normal | ✅ | | | | | |
| case_missing_info | | ✅ | | | | |
| case_tool_failure | | | ✅ | | | |
| case_buget_over | | | | ✅ | | |
| case_duplicate | | | | | ✅ | |
| case_tool_recovery | | | | | | ✅ |

## 已知限制

1. **Mock 模型不等于真实模型**：离线 Mock 仅验证 ReAct 流程正确性，不证明真实 LLM 能做出同样合理的决策
2. **失败恢复仅覆盖 generate_script**：search_material 和 save_plan 失败时直接终止，未实现重试或替代策略
3. **仅两个方案可选**：当前数据只有 plan_A 和 plan_B，多方案场景下的决策逻辑未验证
