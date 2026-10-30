"""ReAct 循环单测：上限、失败不记成功、缺信息、正常路径。"""
import pytest

from src import agent, tools


@pytest.fixture(autouse=True)
def _reset():
    tools.reset()
    yield
    tools.reset()


def _inputs(**kw):
    base = {"topic": "产品发布短视频", "budget": 10, "deadline": "2026-11-10"}
    base.update(kw)
    return base


def test_normal_success():
    report = agent.run(_inputs(), mode="offline")
    assert report.status == "success"
    assert report.saved_plan and report.saved_plan["draft_id"]
    assert report.total_cost == 8


def test_budget_over_replans_to_plan_b():
    report = agent.run(_inputs(), mode="offline")
    costs = [s for s in report.step_status if s["tool"] == "estimate_cost"]
    assert len(costs) >= 2                 # 先 plan_A 超预算，再 plan_B
    assert report.total_cost == 8


def test_missing_budget_incomplete():
    report = agent.run(_inputs(budget=None), mode="offline")
    assert report.status == "incomplete"
    assert "预算" in (report.incomplete_reason or "")


def test_tool_failure_not_counted_success():
    tools.inject_failure("generate_script", times=1)
    report = agent.run(_inputs(), mode="offline")
    # 失败步骤仍记为 ok=False，不混入成功步骤
    gen_fail = [s for s in report.step_status if s["tool"] == "generate_script" and not s["ok"]]
    assert len(gen_fail) == 1
    # Agent 通过替代素材恢复，最终成功
    assert report.status == "success"
    assert report.saved_plan is not None


def test_tool_failure_all_retry_exhausted():
    """所有素材均生成失败时，返回 failed。"""
    tools.inject_failure("generate_script", times=3)
    report = agent.run(_inputs(), mode="offline")
    assert report.status == "failed"
    assert report.saved_plan is None


def test_step_limit_returns_incomplete():
    report = agent.run(_inputs(), mode="offline", max_steps=2)
    assert report.status == "incomplete"
    assert "上限" in (report.incomplete_reason or "")


def test_trace_has_next_action_and_reason():
    report = agent.run(_inputs(), mode="offline")
    assert all("next_action" in s and "reason" in s for s in report.step_status)