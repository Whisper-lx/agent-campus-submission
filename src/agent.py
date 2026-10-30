"""ReAct 主循环：决策 → 执行工具 → 观察回传 → 再决策，直到 finish 或触达上限。

设计要点：
- 模型调用统一走 mock_llm.decide(messages, state, mode)，Mock/真实模型可切换。
- 模型输出做容错：非法 JSON、未知工具、参数缺失都转为可观察的失败，不崩溃。
- 每次工具执行后把结果以 role=tool 追加到 messages，真实模型可复用同一历史。
- 步数/工具调用上限由 state.check_limits 判定，超限返回明确未完成状态。
"""

import json
from typing import Any, Optional

from . import mock_llm, state as st
from .models import AgentState, FinalReport, StepRecord, ToolResult
from .tools import TOOL_REGISTRY


def _append(messages: list[dict], role: str, content: str) -> None:
    messages.append({"role": role, "content": content})


def _validate_action(action: dict) -> Optional[str]:
    """校验模型动作，返回错误说明或 None。"""
    if not isinstance(action, dict):
        return "动作不是 JSON 对象"
    if "action" not in action:
        return "缺少 action 字段"
    return None


def _execute_tool(action: dict, state: AgentState) -> ToolResult:
    """按动作执行工具，统一兜底异常为 ToolResult(ok=False)。"""
    name = action.get("action")
    args = action.get("args") or {}
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return ToolResult(ok=False, tool=str(name), error=f"未知工具 {name}",
                          summary="未知工具")
    if not isinstance(args, dict):
        return ToolResult(ok=False, tool=name, error="args 不是对象", summary="参数非法")
    try:
        return fn(**args)
    except TypeError as e:
        return ToolResult(ok=False, tool=name, error=f"参数不匹配: {e}", summary="参数错误")
    except Exception as e:  # 工具内部异常不终止循环
        return ToolResult(ok=False, tool=name, error=f"工具异常: {e}", summary="工具异常")


def run(inputs: dict, mode: str = "offline", max_steps: int = st.MAX_STEPS,
        max_tool_calls: int = st.MAX_TOOL_CALLS, verbose: bool = False) -> FinalReport:
    """执行一次规划任务，返回最终报告。"""
    state = st.init_state(inputs)
    state.model_mode = mode
    messages: list[dict] = [
        {"role": "user", "content": json.dumps(
            {"topic": state.topic, "budget": state.budget, "deadline": state.deadline},
            ensure_ascii=False)}
    ]
    step_no = 0
    last_rec: Optional[StepRecord] = None

    while True:
        # 1）上限检查：步数+工具调用
        limit_reason = st.check_limits(state, max_steps=max_steps, max_tool_calls=max_tool_calls)
        if limit_reason:
            state.status = "incomplete"
            state.incomplete_reason = limit_reason
            if last_rec:
                last_rec.next_action = "limit_reached"
            break

        # 2） 模型决策
        try:
            action = mock_llm.decide(messages, state, mode=mode)
        except Exception as e:
            state.status = "failed"
            state.incomplete_reason = f"模型调用失败: {e}"
            if last_rec:
                last_rec.next_action = "error"
            break
        if verbose:
            print(f"[decide] {action}")

        # 回填上一步的后续动作
        if last_rec is not None:
            last_rec.next_action = action.get("action", "")

        # 3）动作校验
        err = _validate_action(action)
        if err:
            state.status = "failed"
            state.incomplete_reason = f"模型输出非法: {err}"
            break

        # 4）finish：按模型给的status收尾
        if action["action"] == "finish":
            args = action.get("args") or {}
            status = args.get("status", "success")
            state.status = status if status in ("success", "incomplete", "failed") else "failed"
            state.incomplete_reason = args.get("reason")
            if state.status == "success":
                state.saved = state.saved or bool(args.get("draft_id"))
                state.save_draft_id = state.save_draft_id or args.get("draft_id")
            break

        # 5）执行工具 并回传观察
        step_no += 1
        result = _execute_tool(action, state)
        rec = StepRecord(step_no=step_no, tool=action["action"],
                         args=action.get("args") or {}, result=result,
                         next_action="", reason=action.get("thought", ""))
        if result.ok:
            st.record_success(state, rec)
        else:
            st.record_failure(state, rec)
        last_rec = rec

        observation = {
            "tool": result.tool, "ok": result.ok,
            "data": result.data, "error": result.error, "summary": result.summary,
        }
        _append(messages, "assistant", json.dumps(action, ensure_ascii=False))
        _append(messages, "tool", json.dumps(observation, ensure_ascii=False))

        # 6）成功后若五后续动作由下一轮decide决定：此处记录下一步留给报告
        if verbose:
            print(f"[tool] {result.tool} ok={result.ok} {result.summary}")
    # 7) 兜底：跑完仍 running 视为未完成
    if state.status == "running":
        state.status = "incomplete"
        state.incomplete_reason = state.incomplete_reason or "循环结束但未达成目标"
    return st.build_report(state)