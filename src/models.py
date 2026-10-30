"""数据模型：对齐第2题交付结果字段。"""
# 职责：定义所有结构化数据模型，字段对齐题目“交付结果”：任务计划、步骤状态、工具结果、费用合计、已保存方案或未完成原因

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    """工具统一返回结构。"""
    ok: bool
    tool: str
    data: Any = None
    error: Optional[str] = None
    summary: str = ""          # 返回摘要，写入 Trace


@dataclass
class StepRecord:
    """单个步骤记录，用于 Trace 与状态保留。"""
    step_no: int
    tool: str
    args: dict
    result: ToolResult
    next_action: str = ""      # 模型后续动作
    reason: str = ""           # 简要决策依据（不写内部思维）


@dataclass
class PlanCandidate:
    """候选方案。"""
    name: str
    desc: str
    estimated_cost: float
    steps: list[str] = field(default_factory=list)


@dataclass
class AgentState:
    """运行状态：由 state.py 维护，agent.py 读写。"""
    budget: Optional[float] = None
    deadline: Optional[str] = None
    topic: Optional[str] = None
    materials: list[dict] = field(default_factory=list)
    completed_steps: list[StepRecord] = field(default_factory=list)  # 仅成功
    failed_steps: list[StepRecord] = field(default_factory=list)     # 失败，不记成功
    total_cost: float = 0.0
    selected_plan: Optional[str] = None
    saved: bool = False
    save_draft_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    step_count: int = 0
    tool_call_count: int = 0
    status: str = "running"    # running / success / incomplete / failed
    incomplete_reason: Optional[str] = None


@dataclass
class FinalReport:
    """最终交付结果，main.py 打印、examples 输出用。"""
    task_plan: list[str]
    step_status: list[dict]
    tool_results: list[dict]
    total_cost: float
    saved_plan: Optional[dict]
    status: str
    incomplete_reason: Optional[str] = None