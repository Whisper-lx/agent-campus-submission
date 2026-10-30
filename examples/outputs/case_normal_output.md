# 运行结果：case_normal（mode=offline）

- 状态：`success`
- 费用合计：8

## 任务计划
1. search_material
2. generate_script
3. estimate_cost
4. estimate_cost
5. save_plan

## 步骤状态
| 步骤 | 工具 | 成功 | 摘要 |
|---|---|---|---|
| 1 | search_material | True | 命中 2 条素材: ['M01', 'M02'] |
| 2 | generate_script | True | 已生成脚本，引用 M01 |
| 3 | estimate_cost | True | plan_A 估算 12，预算 10，超预算 |
| 4 | estimate_cost | True | plan_B 估算 8，预算 10，在预算内 |
| 5 | save_plan | True | 已保存草稿 draft_001（仅草稿，未发布） |

## 工具结果
- `search_material` ok=True：命中 2 条素材: ['M01', 'M02']
- `generate_script` ok=True：已生成脚本，引用 M01
- `estimate_cost` ok=True：plan_A 估算 12，预算 10，超预算
- `estimate_cost` ok=True：plan_B 估算 8，预算 10，在预算内
- `save_plan` ok=True：已保存草稿 draft_001（仅草稿，未发布）

## 已保存方案
- 草稿 ID：`draft_001`
- 方案：`plan_B`
- 仅草稿，未真实发布
