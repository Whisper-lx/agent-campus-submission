# 内容任务规划 Agent

帮助运营人员在预算与截止时间内完成一份内容活动方案的 AI Agent，基于 ReAct（Reasoning + Acting）决策循环实现。

## 题目

项目题 · 内容任务规划 Agent

## 技术选型

- 语言：Python 3.10+
- 框架：原生实现，无第三方 Agent 框架依赖
- 模型：离线 Mock 模式（预设规则模拟决策）+ 可切换真实 LLM
- 测试：pytest

## 项目结构

```
├── src/
│   ├── main.py          # CLI 入口，加载用例、运行 Agent、输出报告
│   ├── agent.py         # ReAct 主循环：决策 → 执行 → 观察 → 再决策
│   ├── mock_llm.py      # 模型接入层：Mock 决策 + 真实 LLM 接口
│   ├── tools.py         # 工具层：素材检索、脚本生成、成本估算、方案保存
│   ├── models.py        # 数据模型：ToolResult、StepRecord、AgentState、FinalReport
│   └── state.py         # 状态管理：初始化、上限检查、步骤登记、报告组装
├── tests/
│   ├── test_tools.py        # 工具层单测
│   ├── test_agent_loop.py   # ReAct 循环单测
│   └── test_acceptance.py   # 五项验收点测试
├── data/
│   ├── materials.json   # 合成素材库
│   ├── tool_costs.json  # 方案成本与工具费用表
│   └── rules.md         # 业务规则
├── examples/
│   ├── inputs/          # 5 组测试用例输入
│   ├── outputs/         # 运行输出（Markdown）
│   └── traces/          # 运行记录（JSONL）
├── docs/                # 设计与评估文档
├── requirements.txt
├── .env.example
└── README.md
```

## 环境准备

```bash
# Python 3.10+
pip install -r requirements.txt
```

## 运行

```bash
# 离线 Mock 模式（默认）
python -m src.main --case case_normal --offline
python -m src.main --case case_missing_info --offline
python -m src.main --case case_tool_failure --offline
python -m src.main --case case_buget_over --offline
python -m src.main --case case_duplicate --offline
python -m src.main --case case_tool_recovery --offline

# 带详细日志
python -m src.main --case case_normal --offline --verbose

# 真实 LLM 模式（需配置环境变量）
# Linux
export LLM_API_KEY=sk-xxx
python -m src.main --case case_normal --real
# Windows 
set LLM_API_KEY=sk-xxx
python -m src.main --case case_normal --real
```

输出自动归档到 `examples/outputs/`（Markdown 报告）和 `examples/traces/`（JSONL 运行记录）。

## 测试

```bash
python -m pytest tests/ -v
```

## 用例说明

| 用例 | 场景 | 预期状态 |
|---|---|---|
| case_normal | 正常完成，plan_A 超预算后改选 plan_B | success |
| case_missing_info | 缺预算和截止时间 | incomplete |
| case_tool_failure | 注入 save_plan 失败 | failed |
| case_buget_over | 所有方案均超预算，返回缺口 | incomplete |
| case_duplicate | 重复执行，验证幂等保存 | success（同一草稿 ID）|
| case_tool_recovery | 注入 generate_script 失败，续跑恢复 | success（改用 M02）|

## 评审入口

- 设计文档：[docs/02-solution.md](docs/02-solution.md)
- 测试与评估：[docs/03-evaluation.md](docs/03-evaluation.md)
- 运行记录：[examples/traces/](examples/traces/)
- 验收测试：`python -m pytest tests/test_acceptance.py -v`
