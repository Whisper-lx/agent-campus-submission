"""模型接入层：统一 decide 接口，Mock 与真实模型可切换。

边界声明：
- offline 模式用预设规则模拟决策，仅验证 ReAct 流程，不证明真实模型效果。
- real 模式接入真实 LLM，需实现 _decide_real()，返回结构保持一致。
"""
import json
import os
from typing import Any, Optional

from .models import AgentState
from .tools import TOOL_DESCRIPTIONS

ACTION_SCHEMA_HINT = (
    "只输出 JSON：{\"thought\": str, \"action\": str, \"args\": obj}。"
    "action 取工具名之一，或 \"finish\"。finish 时 args 含 status/reason。"
)


def decide(messages: list[dict], state: AgentState, mode: str = "offline") -> dict:
    """统一决策入口。mode: offline(Mock) / real(真实模型)。"""
    if mode == "real":
        return _decide_real(messages, state)
    return _decide_mock(messages, state)


def _last_tool(messages: list[dict]) -> Optional[dict]:
    for m in reversed(messages):
        if m.get("role") == "tool":
            try:
                return json.loads(m["content"])
            except (json.JSONDecodeError, TypeError):
                return None
    return None


def _find_search_results(messages: list[dict]) -> list[dict]:
    """从消息历史中提取素材检索结果，用于失败后重试其他素材。"""
    for m in messages:
        if m.get("role") == "tool":
            try:
                data = json.loads(m["content"])
                if data.get("tool") == "search_material" and data.get("ok") and data.get("data"):
                    return data["data"]
            except (json.JSONDecodeError, TypeError):
                pass
    return []


def _decide_mock(messages: list[dict], state: AgentState) -> dict:
    if not state.budget or not state.deadline:
        return {"thought": "预算或截止时间缺失", "action": "finish",
                "args": {"status": "incomplete",
                         "reason": "缺少预算或截止时间，请补充后重试"}}
    last = _last_tool(messages)
    if last is None:
        return {"thought": "先检索素材", "action": "search_material",
                "args": {"topic": state.topic or ""}}
    tool = last.get("tool")
    if tool == "search_material":
        if not last.get("data"):
            return {"thought": "无素材，请求补充", "action": "finish",
                    "args": {"status": "incomplete", "reason": "未检索到可用素材"}}
        mid = last["data"][0]["id"]
        return {"thought": f"用 {mid} 生成脚本，按 plan_A",
                "action": "generate_script",
                "args": {"material_id": mid, "plan_name": "plan_A"}}
    if tool == "generate_script":
        if not last.get("ok"):
            tried_ids = {s.args.get("material_id") for s in
                         state.failed_steps + state.completed_steps
                         if s.tool == "generate_script"}
            materials = _find_search_results(messages)
            for m in materials:
                if m["id"] not in tried_ids:
                    return {"thought": f"生成失败，改用素材 {m['id']} 重试，保留已成功步骤",
                            "action": "generate_script",
                            "args": {"material_id": m["id"], "plan_name": "plan_B"}}
            return {"thought": "所有素材均生成失败", "action": "finish",
                    "args": {"status": "failed", "reason": "脚本生成失败，已尝试所有可用素材"}}
        plan = last["data"]["plan"]
        return {"thought": f"估算 {plan} 成本", "action": "estimate_cost",
                "args": {"plan_name": plan, "budget": state.budget}}
    if tool == "estimate_cost":
        data = last.get("data") or {}
        if data.get("over_budget") is True:
            if data.get("plan") == "plan_B":
                cost = data.get("cost", 0)
                gap = cost - (state.budget or 0)
                return {"thought": "替代方案仍超预算，无可行方案", "action": "finish",
                        "args": {"status": "incomplete",
                                 "reason": f"预算 {state.budget} 不足，最低方案 plan_B 估算 {cost}，缺口 {gap}"}}
            return {"thought": "超预算，改选 plan_B 重新估算",
                    "action": "estimate_cost",
                    "args": {"plan_name": "plan_B", "budget": state.budget}}
        return {"thought": "成本可行，保存草稿", "action": "save_plan",
                "args": {"idempotency_key": state.idempotency_key,
                         "plan_name": state.selected_plan or data.get("plan", "plan_B"),
                         "script": "（脚本见生成步骤）"}}
    if tool == "save_plan":
        if not last.get("ok"):
            return {"thought": "保存失败", "action": "finish",
                    "args": {"status": "failed", "reason": "草稿保存失败"}}
        return {"thought": "草稿已保存，结束", "action": "finish",
                "args": {"status": "success", "draft_id": last["data"]["draft_id"]}}
    return {"thought": "无法继续", "action": "finish",
            "args": {"status": "failed", "reason": "无法继续决策"}}


def _build_real_prompt(messages: list[dict], state: AgentState) -> list[dict]:
    """构造真实模型消息：系统提示含工具描述、动作 schema、业务约束。"""
    tools_desc = "\n".join(f"- {k}: {v}" for k, v in TOOL_DESCRIPTIONS.items())
    system = (
        "你是内容任务规划 Agent。可用工具：\n" + tools_desc +
        "\n约束：预算不足时换替代方案重估算；缺预算/截止时间须请求补充；"
        "仅保存草稿不得发布；失败不得记成功。\n" + ACTION_SCHEMA_HINT
    )
    return [{"role": "system", "content": system}] + messages


def _decide_real(messages: list[dict], state: AgentState) -> dict:
    """真实模型接入点：环境变量提供密钥与模型名。

    返回结构必须与 Mock 一致，agent 循环无需改动。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    if not api_key:
        raise RuntimeError("LLM_API_KEY 未配置；可改用 --offline 走 Mock。")
    try:
        from openai import OpenAI   # 后面可能接入deepseek-flash
    except ImportError as e:
        raise RuntimeError("未安装 openai；pip install openai 或使用 --offline。") from e
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",)
    resp = client.chat.completions.create(
        model=model,
        messages=_build_real_prompt(messages, state),
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = resp.choices[0].message.content
    try:
        action = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"模型输出非 JSON：{content}") from e
    if "action" not in action:
        raise RuntimeError(f"模型输出缺少 action：{action}")
    return action