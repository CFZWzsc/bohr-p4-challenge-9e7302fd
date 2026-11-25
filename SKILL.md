---
name: methods-and-statistics-audit
description: Use when a manuscript's methods and statistics must be reviewed for inferential defensibility, requiring checks of control, randomisation, blinding, sample size, power, named tests, p-value reporting, effect sizes, confidence intervals, multiplicity, missing data, contradictions between significance wording and p-values, and explicit unverifiable items.
---

# 研究方法与统计审查

## 用途与适用条件

当任务要求审查「这个结论在方法上站不站得住」时使用：逐项检查对照、随机、盲法、样本量、功效、检验名称、p 值报告、效应量与置信区间、多重比较、缺失数据与前提假设，并交叉核对显著性表述与 p 值、摘要与方法样本量是否一致。

**适用前提**：`case.json` 提供稿件正文或章节映射。无方法/结果章节时退化为全文检查并降级为 `partial`。

**不适用**：重算统计量、判断具体检验是否最优、替代统计学家复核、访问原始数据或代码。

## Quickstart

包内自带一个合成演示案例，可直接跑通：

```powershell
python scripts/run_skill.py --case examples/demo-case/case.json --out "$env:TEMP\demo_9e7302fd\result.json" --work "$env:TEMP\demo_9e7302fd\work"
```

- 演示输入：`examples/demo-case/case.json`，4 章节合成稿件（11 项统计报告检查里 6 项未报告；摘要 120 例与方法 96 例不一致）。
- 输出：`$env:TEMP\demo_9e7302fd\result.json`，`status=success`，10 条 findings（2 high / 7 medium / 1 low），`verdict.decision=major_revision`。
- `output_contract` 的 `issues`、`summary`、`verdict` 三个键均非空；同一输入连续两次运行的 result.json 字节一致。

> 案例文本为合成内容，不代表任何真实论文或官方评测数据。

## 输入

| 输入 | 说明 |
|---|---|
| `/input/case.json` | `manuscript`/`paper`/`text`，可为整段文本或 `{Abstract, Methods, Results, ...}` 章节映射。 |
| `task.md` | 可选，无稿件字段时使用。 |
| `--work` | 默认 `/app/work`。 |

## 处理流程

1. **设计检查**（正确性）：对照条件、随机化、盲法三项，缺项给 high/medium/low 与修改动作。
2. **抽样检查**（正确性）：样本量、功效/样本量计算、缺失与脱落，区分「未报告」与「未做」。
3. **统计报告**（完整性）：检验名称、效应量、置信区间、多重比较校正、前提假设逐项核对。
4. **推断一致性**（正确性）：同一句声称显著但所有 p>0.05，或声称无差异但 p≤0.05，均记 high；只有阈值 p 且无 CI 记 medium。
5. **可重复性**（完整性）：摘要与方法样本量不一致记 high；列出未提供的原始数据、代码与补充材料。
6. **交付**（可核验性）：每条 finding 带 facet、severity、locator、quote、evidence、recommendation，并生成修改清单。

## 输出契约

顶层：`case_id`、`status`、`result`、`checks`、`review_report`、`evidence`、`uncertainty`、`errors`、`stats`、`contract_notes`、`output_contract_fields`。同时写出 `review-report.md`（可直接交付的方法与统计审查报告）。

`result` 含：`sections_detected`、`checks`、`p_values_found`、`sample_sizes`、`findings`、`summary`（total/by_severity/missing_core_items/verdict）、`revision_checklist`、`unverifiable`、`limitations`、`change_log`。

输入 `output_contract` 的字段名全部保留；无法产出写 `null` 并在 `contract_notes` 说明。

`status`：无正文 → `insufficient_input`；缺方法或结果/摘要章节 → `partial`；齐备 → `success`；解析失败 → `failed`。

## 异常处理

| 情形 | 处理 | 标记 |
|---|---|---|
| 无方法章节 | 全文检查并降级 | `status=partial` |
| 无 p 值 | 不推断显著性 | `check=statistics_reporting` |
| 只写 p<0.05 | 记 medium，要求精确值与 CI | `facet=statistics_reporting` |
| 显著性与 p 值矛盾 | 记 high | `facet=inference_validity` |
| 摘要/方法样本量不一致 | 记 high | `facet=reproducibility` |
| 未提供数据与代码 | 列入不可核验 | `unverifiable` |
| 输出不可写 | stderr 错误，退出码 3 | 无静默成功 |

## 限制

- 只审查报告，不判断所选检验是否最适合该设计。
- 无原始数据与分析代码，不重算任何统计量。
- 「未报告」不等于「未执行」，findings 中已显式区分。
- 严重度表示若缺口属实的推断风险，不是学术不端结论。

## 最小调用示例（示例，非正式案例结果）

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

```json
{"case_id":"demo-ms-01","manuscript":{"Abstract":"Scores improved significantly in 120 patients (p=0.21).",
 "Methods":"We enrolled 100 patients with a control group and used a t test.","Results":"Scores improved significantly (p=0.21).","Discussion":"...","Conclusion":"..."}}
```

示意输出（示例）：`{"status":"success","result":{"summary":{"by_severity":{"high":2},"verdict":"major_statistical_revision"}}}`。不代表任何官方固定案例结果。


## 交付要求

- 运行：`python scripts/run_skill.py --case /input/case.json --out /app/output/result.json`（`--output` 等价）。
- 单次运行产出完整成品：`result.json`（契约字段齐全）与 `review-report.md`（可直接复核的方法与统计审查报告）。
- 每个问题附定位、原文、判定、依据与修改建议；覆盖输入中的全部章节与检查项，不静默跳过。
- 输入缺失、JSON 损坏或输出不可写时，仍写出结构化 `result.json` 并正常退出；未检查项写入 `uncertainty` / `limitations`，不伪造内容。
- 结果由输入驱动，保持确定性（同一输入双跑字节一致）；不联网、不声称平台评分。

## 输入发现与伴随产物

- 输入发现：除 `case.json` 字段外，运行时会扫描其所在目录的 `manuscript.md`、`paper.txt`、`*.json`、`*.jsonl`、`*.csv` 等真实文件并合并；按内容判断稿件/参考文献角色，文件名不作标签；发现清单写入 `provenance.json`。
- 伴随产物（单次运行同时写出）：`review.json`、`checklist.csv`、`report.md`、`provenance.json`、`validation.json`。`output_contract` 字段若对应这些产物，`result.json` 直接给出文件名并在 `contract_notes` 说明。
- `validation.json` 记录契约覆盖、计数对账与引文核验结果（`locator_status.n_locator_issues`）。
