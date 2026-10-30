# 运行结果：case_tool_failure（mode=offline）

- 状态：`failed`
- 未完成原因：草稿保存失败
- 费用合计：8

## 任务计划
1. search_material
2. generate_script
3. estimate_cost
4. estimate_cost

## 步骤状态
| 步骤 | 工具 | 成功 | 摘要 |
|---|---|---|---|
| 1 | search_material | True | 命中 2 条素材: ['M01', 'M02'] |
| 2 | generate_script | True | 已生成脚本，引用 M01 |
| 3 | estimate_cost | True | plan_A 估算 12，预算 10，超预算 |
| 4 | estimate_cost | True | plan_B 估算 8，预算 10，在预算内 |
| 5 | save_plan | False | 工具失败 |

## 工具结果
- `search_material` ok=True：命中 2 条素材: ['M01', 'M02']
- `generate_script` ok=True：已生成脚本，引用 M01
- `estimate_cost` ok=True：plan_A 估算 12，预算 10，超预算
- `estimate_cost` ok=True：plan_B 估算 8，预算 10，在预算内
- `save_plan` ok=False：工具失败

## 已保存方案
（未保存）
