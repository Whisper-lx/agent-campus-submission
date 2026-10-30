"""运行状态管理：初始化、上限、幂等、步骤登记、报告组装。"""
# 职责：状态初始化、上限检查、幂等键生成、成功/失败步骤登记、最终报告组装。把状态变更逻辑集中在这里，agent.py 只管循环。

import hashlib
import json
from typing import Optional

from .models import AgentState, StepRecord, ToolResult, FinalReport

MAX_STEPS = 8          # 执行步数上限
MAX_TOOL_CALLS = 12    # 工具调用次数上限


def make_idempotency_key(topic: str, budget: Optional[float], deadline: Optional[str]) -> str:
    """相同请求生成相同幂等键，用于防重复保存。"""
    raw = json.dumps({"topic": topic, "budget": budget, "deadline": deadline}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def init_state(inputs: dict) -> AgentState:
    """从输入初始化状态。缺字段保持 None，交给模型请求补充。"""
    state = AgentState(
        budget=inputs.get("budget"),
        deadline=inputs.get("deadline"),
        topic=inputs.get("topic"),
        idempotency_key=make_idempotency_key(
            inputs.get("topic", ""), inputs.get("budget"), inputs.get("deadline")
        ),
    )
    return state


def check_limits(state: AgentState, max_steps: int = MAX_STEPS,
                  max_tool_calls: int = MAX_TOOL_CALLS) -> Optional[str]:
    """返回超限原因，未超限返回 None。"""
    if state.step_count >= max_steps:
        return f"达到执行步数上限 {max_steps}"
    if state.tool_call_count >= max_tool_calls:
        return f"达到工具调用次数上限 {max_tool_calls}"
    return None


def record_success(state: AgentState, rec: StepRecord) -> None:
    state.completed_steps.append(rec)
    state.step_count += 1
    state.tool_call_count += 1
    if rec.tool == "estimate_cost" and isinstance(rec.result.data, dict):
        state.total_cost = rec.result.data.get("cost", state.total_cost)
        if rec.result.data.get("over_budget") is False:
            state.selected_plan = rec.result.data.get("plan", state.selected_plan)


def record_failure(state: AgentState, rec: StepRecord) -> None:
    """失败不记入 completed_steps。"""
    state.failed_steps.append(rec)
    state.step_count += 1
    state.tool_call_count += 1


def build_report(state: AgentState) -> FinalReport:
    task_plan = [s.tool for s in state.completed_steps]
    step_status = [
        {"step_no": s.step_no, "tool": s.tool, "args": s.args,
         "ok": s.result.ok, "summary": s.result.summary,
         "next_action": s.next_action, "reason": s.reason}
        for s in state.completed_steps + state.failed_steps
    ]
    tool_results = [
        {"tool": s.tool, "ok": s.result.ok, "summary": s.result.summary}
        for s in state.completed_steps + state.failed_steps
    ]
    saved_plan = (
        {"draft_id": state.save_draft_id, "plan": state.selected_plan}
        if state.saved else None
    )
    return FinalReport(
        task_plan=task_plan,
        step_status=step_status,
        tool_results=tool_results,
        total_cost=state.total_cost,
        saved_plan=saved_plan,
        status=state.status,
        incomplete_reason=state.incomplete_reason,
    )