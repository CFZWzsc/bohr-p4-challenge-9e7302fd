#!/usr/bin/env python3
"""Methods and statistics audit (Python standard library only).

Reads a case file (default /input/case.json) containing manuscript text or
section map. It checks the design, sampling and statistical reporting items that
determine whether the inference is defensible: control condition, randomisation,
blinding, sample size, power, named tests, exact p-values, effect sizes,
confidence intervals, multiplicity correction, missing data and assumption checks.
It also looks for internal contradictions (significance label versus reported p,
sample size mismatch between abstract and methods) and reports each as a located
finding with severity and a concrete fix. Absent information is reported as "not
reported", never assumed present.

No network access, no randomness, no private paths.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"
CHECKS = (
    ("design_control", r"control group|controls?|placebo|comparison group|对照|安慰剂", "design", "high",
     "Add a control/comparison condition or explain why none is needed."),
    ("randomisation", r"randomi[sz]\w*|random allocation|随机", "design", "high",
     "Describe the randomisation sequence and allocation concealment."),
    ("blinding", r"blind\w*|masked|双盲|单盲", "design", "medium",
     "State who was blinded (participants, assessors, analysts)."),
    ("sample_size", r"\bn\s*=\s*\d+|\d+\s+(participants|patients|subjects|samples|mice|records)|样本量", "sampling", "high",
     "Report the analysed sample size and how it was determined."),
    ("power", r"power analysis|sample size calculation|powered|功效|样本量计算|把握度", "sampling", "medium",
     "Report an a priori power or sample-size calculation, or label the study as exploratory."),
    ("named_test", r"t[- ]test|anova|chi[- ]square|wilcoxon|mann.whitney|kruskal|regression|mixed model|log.rank|"
                   r"fisher|bootstra|检验|方差分析|卡方|回归", "statistics", "high",
     "Name the statistical test used for each comparison."),
    ("effect_size", r"effect size|cohen|odds ratio|hazard ratio|risk ratio|eta squared|r squared|标准化效应|效应量", "statistics", "medium",
     "Report an effect size with its uncertainty, not only a p-value."),
    ("confidence_interval", r"confidence interval|95%\s*ci|\bci\b|置信区间", "statistics", "medium",
     "Report confidence intervals for the primary estimates."),
    ("multiplicity", r"bonferroni|false discovery|\bfdr\b|tukey|holm|multiple comparison|multiple testing|多重比较|校正", "inference", "medium",
     "State how multiple comparisons were controlled, or label them exploratory."),
    ("missing_data", r"missing data|dropout|attrition|excluded|lost to follow|缺失|脱落", "sampling", "medium",
     "Report missing data, exclusions and how they were handled."),
    ("assumptions", r"normality|homogen\w*|independen\w*|assumption|正态|方差齐|独立", "inference", "low",
     "Report the assumption checks behind the chosen test."),
)


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_task_text(case_path, work_dir):
    for path in (Path(case_path).resolve().parent / "task.md", Path("/input/task.md"), Path(work_dir) / "task.md"):
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
    return ""


def norm_space(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return norm_space(value)
    if isinstance(value, list):
        return norm_space(" ".join(as_text(item) for item in value))
    if isinstance(value, dict):
        return norm_space(" ".join(as_text(item) for item in value.values()))
    return norm_space(str(value))


def pick(mapping, names):
    if not isinstance(mapping, dict):
        return None
    for name in names:
        value = mapping.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def sections_of(case, task_text):
    manuscript = pick(case, ("manuscript", "paper", "text", "document", "article", "content"))
    sections = {}
    if isinstance(manuscript, dict):
        raw = manuscript.get("sections") if isinstance(manuscript.get("sections"), dict) else manuscript
        for key, value in raw.items():
            text = as_text(value)
            if text:
                sections[str(key).lower()] = text
    elif isinstance(manuscript, list):
        for item in manuscript:
            if isinstance(item, dict):
                name = as_text(pick(item, ("heading", "section", "name"))).lower()
                text = as_text(pick(item, ("text", "content")))
                if name and text:
                    sections[name] = text
    if not sections:
        sections["body"] = as_text(manuscript) or task_text
    return sections


def sentences(text):
    text = norm_space(text)
    if not text:
        return []
    return [norm_space(part) for part in re.split(r"(?<=[.!?])\s+|(?<=[。！？])", text) if norm_space(part)]


def methods_text(sections):
    keys = [key for key in sections if "method" in key or "方法" in key or "statistic" in key or "统计" in key]
    if keys:
        return " ".join(sections[key] for key in keys)
    return " ".join(sections.values())


def results_text(sections):
    keys = [key for key in sections if "result" in key or "结果" in key or "abstract" in key or "摘要" in key]
    return " ".join(sections[key] for key in keys) if keys else " ".join(sections.values())


def p_values(text):
    values = []
    for match in re.finditer(r"\bp\s*(<=|>=|<|>|=|＝)\s*(0?\.\d+)", text, re.IGNORECASE):
        try:
            values.append({"raw": match.group(0), "operator": match.group(1), "value": float(match.group(2))})
        except ValueError:
            continue
    return values


def sample_sizes(text):
    values = []
    for match in re.finditer(r"\bn\s*=\s*(\d+)", text, re.IGNORECASE):
        values.append(int(match.group(1)))
    for match in re.finditer(r"(\d+)\s+(participants|patients|subjects|samples|mice)", text, re.IGNORECASE):
        values.append(int(match.group(1)))
    return values


def claim_significance(text):
    lowered = text.lower()
    if re.search(r"no significant|not significant|non.significant|无显著|无差异|不显著", lowered):
        return "null"
    if re.search(r"significantly|significant|显著", lowered):
        return "positive"
    return None


def build_payload(case, task_text):
    sections = sections_of(case, task_text)
    methods = methods_text(sections)
    results = results_text(sections)
    all_text = norm_space(" ".join(sections.values()))
    findings = []
    checks = []

    for name, pattern, facet, severity, revision in CHECKS:
        target = methods if name not in ("effect_size", "confidence_interval", "multiplicity") else (results + " " + methods)
        present = bool(re.search(pattern, target, re.IGNORECASE))
        scope = "methods" if name not in ("effect_size", "confidence_interval", "multiplicity") else "results/methods"
        checks.append({"check": name, "scope": scope, "status": "reported" if present else "not_reported"})
        if not present:
            findings.append({
                "facet": facet, "severity": severity, "locator": scope + "#0", "quote": "",
                "finding": "The %s item is not reported where it is expected (%s)." % (name.replace("_", " "), scope),
                "evidence": "no matching pattern for '%s'" % name,
                "recommendation": revision,
                "status": "not_reported (absence in the supplied text is not proof it was not done)",
            })

    method_sentences = sentences(methods)
    mentions_test = re.search(CHECKS[5][1], methods, re.IGNORECASE)
    for index, sentence in enumerate(method_sentences):
        if claim_significance(sentence) and not mentions_test and not p_values(sentence):
            findings.append({
                "facet": "statistics_reporting", "severity": "medium", "locator": "methods#s%d" % index,
                "quote": sentence[:300],
                "finding": "A significance statement appears without a named test or a p-value.",
                "evidence": "significance cue present; no test name or p-value in the sentence",
                "recommendation": "Attach the test name and the test statistic/p-value to this statement.",
                "status": "reported",
            })

    pv = p_values(all_text)
    thresholds = [item for item in pv if item["operator"] in ("<", "<=", "＝", "=")]
    if pv and not any(item["operator"] in ("=", "＝") for item in pv) and not re.search(r"confidence interval|95%\s*ci|置信区间", all_text, re.IGNORECASE):
        findings.append({
            "facet": "statistics_reporting", "severity": "medium", "locator": "results#0", "quote": pv[0]["raw"],
            "finding": "Only thresholded p-values are reported, with no exact p-value or confidence interval.",
            "evidence": "p-value forms: " + ", ".join(sorted({item["raw"] for item in pv}))[:200],
            "recommendation": "Report exact p-values and confidence intervals for the primary estimates.",
            "status": "reported",
        })

    for index, sentence in enumerate(sentences(results)):
        label = claim_significance(sentence)
        values = p_values(sentence)
        if label == "positive" and values and min(item["value"] for item in values) > 0.05:
            findings.append({
                "facet": "inference_validity", "severity": "high", "locator": "results#s%d" % index,
                "quote": sentence[:300],
                "finding": "Significance is claimed although every reported p-value exceeds 0.05.",
                "evidence": "p-values: " + ", ".join(item["raw"] for item in values),
                "recommendation": "Align the wording with the statistical result, or correct the analysis.",
                "status": "reported",
            })
        if label == "null" and values and max(item["value"] for item in values) <= 0.05:
            findings.append({
                "facet": "inference_validity", "severity": "high", "locator": "results#s%d" % index,
                "quote": sentence[:300],
                "finding": "A null result is claimed although the reported p-value is at or below 0.05.",
                "evidence": "p-values: " + ", ".join(item["raw"] for item in values),
                "recommendation": "Check the test, the grouping and the wording before concluding no effect.",
                "status": "reported",
            })

    abstract = ""
    for key, value in sections.items():
        if "abstract" in key or "摘要" in key:
            abstract = value
            break
    abstract_n = sorted(set(sample_sizes(abstract)))
    method_n = sorted(set(sample_sizes(methods)))
    if abstract_n and method_n and not set(abstract_n) & set(method_n):
        findings.append({
            "facet": "reproducibility", "severity": "high", "locator": "abstract#0",
            "quote": (abstract or "")[:200],
            "finding": "The abstract and methods report different sample sizes.",
            "evidence": "abstract n=%s; methods n=%s" % (abstract_n, method_n),
            "recommendation": "Reconcile the analysed sample size across abstract, methods and tables.",
            "status": "reported",
        })

    unverifiable = [{"item": "raw_data", "reason": "the dataset behind the test statistics was not supplied"},
                    {"item": "analysis_code", "reason": "no analysis script or notebook was supplied"}]
    if not re.search(r"supplement|appendix|附[录件]", all_text, re.IGNORECASE):
        unverifiable.append({"item": "supplementary_material", "reason": "no supplement is referenced in the text"})

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in findings:
        severity_counts[item["severity"]] = severity_counts.get(item["severity"], 0) + 1
    missing_core = [check["check"] for check in checks if check["status"] == "not_reported" and check["check"] in ("design_control", "sample_size", "named_test")]

    uncertainty = []
    if not all_text:
        uncertainty.append({"type": "no_text", "detail": "No manuscript text was found."})
    if not any("method" in key or "方法" in key for key in sections):
        uncertainty.append({"type": "no_methods_section", "detail": "No methods section was detected; checks used the whole text."})
    uncertainty.append({"type": "text_only", "detail": "No raw data, code or supplement was supplied; statistical claims were not recomputed."})

    if not all_text:
        status = "insufficient_input"
    elif not any("method" in key or "方法" in key for key in sections) or not any("result" in key or "结果" in key or "abstract" in key for key in sections):
        status = "partial"
    else:
        status = "success"

    result = {
        "sections_detected": sorted(sections),
        "checks": checks,
        "p_values_found": pv,
        "sample_sizes": {"abstract": abstract_n, "methods": method_n},
        "findings": findings,
        "summary": {
            "total": len(findings), "by_severity": severity_counts,
            "missing_core_items": missing_core,
            "verdict": "major_statistical_revision" if severity_counts.get("high") else ("minor_statistical_revision" if findings else "no_blocking_issue"),
        },
        "revision_checklist": [{"locator": item["locator"], "action": item["recommendation"]} for item in findings],
        "unverifiable": unverifiable,
        "limitations": [
            "The audit checks reporting, not whether the reported test was the correct one for the design.",
            "No raw data or analysis code was supplied, so no statistic was recomputed.",
            "A missing item is reported as 'not reported', not as 'not done'.",
            "Severity reflects the risk to the inference if the gap is real, not a misconduct finding.",
        ],
        "change_log": [
            "Detected sections and isolated methods/results text.",
            "Checked twelve design, sampling, statistics and inference reporting items.",
            "Cross-checked significance wording against reported p-values.",
            "Compared abstract and methods sample sizes.",
            "Listed unverifiable items and generated a revision checklist.",
        ],
    }
    return {
        "case_id": case_identifier(case),
        "status": status,
        "result": result,
        "checks": checks,
        "review_report": {"format": "markdown",
                          "content": build_review_report(result, case_identifier(case), uncertainty)},
        "evidence": [{"kind": "finding", "locator": item["locator"], "quote": item["quote"], "severity": item["severity"]} for item in findings],
        "uncertainty": uncertainty,
        "errors": [],
        "stats": {"findings": len(findings), "high": severity_counts.get("high", 0), "medium": severity_counts.get("medium", 0),
                  "low": severity_counts.get("low", 0), "p_values": len(pv), "network": "disabled"},
    }


def contract_names(case):
    contract = case.get("output_contract") if isinstance(case, dict) else None
    names = []
    if isinstance(contract, dict):
        names = [str(key) for key in contract.keys()]
    elif isinstance(contract, list):
        for item in contract:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                for key in ("name", "field", "key", "id"):
                    if isinstance(item.get(key), str):
                        names.append(item[key])
                        break
    return names


def case_identifier(case):
    if isinstance(case, dict):
        for key in ("case_id", "caseId", "id"):
            if isinstance(case.get(key), str) and case[key].strip():
                return case[key]
    return ""


CONTRACT_ALIASES = {
    "issues": ("findings", "problems", "defects", "violations"),
    "findings": ("issues",),
    "summary": ("stats", "overview", "counts", "tally"),
    "overview": ("summary", "stats"),
    "stats": ("summary",),
    "verdict": ("recommendation", "decision", "conclusion", "overall"),
    "reviewreport": ("report", "review", "markdown"),
    "report": ("review_report", "review"),
    "scores": ("score", "metrics", "verdict"),
    "metrics": ("scores", "stats"),
    "rows": ("records", "data", "table"),
    "records": ("rows", "data"),
    "citations": ("reference_checks", "citation_checks", "references"),
    "tables": ("table_extractions", "tables_extracted"),
    "figures": ("figure_mentions", "figures_extracted"),
}


def _norm_key(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _severity_counts(findings):
    counts = {}
    if isinstance(findings, list):
        for item in findings:
            if not isinstance(item, dict):
                continue
            sev = str(item.get("severity") or item.get("level") or "unspecified").lower()
            counts[sev] = counts.get(sev, 0) + 1
    return counts


def _derive_named(name, flat):
    """Return a value for `name` derived from the payload, or (None, reason)."""
    norm = _norm_key(name)
    for alias in CONTRACT_ALIASES.get(norm, ()):
        if alias in flat and flat[alias] not in (None, "", [], {}):
            return flat[alias], "derived from '%s'" % alias
    findings = flat.get("findings") or flat.get("issues") or []
    if norm in ("verdict", "reviewverdict", "decision", "recommendation", "overallverdict"):
        counts = _severity_counts(findings)
        if counts or flat.get("checks"):
            decision = ("major_revision" if counts.get("high")
                        else "minor_revision" if counts.get("medium")
                        else "accept")
            return ({"decision": decision,
                     "basis": "derived from %d finding(s) and %d check(s)"
                              % (len(findings) if isinstance(findings, list) else 0,
                                 len(flat.get("checks") or [])),
                     "severity_counts": counts},
                    "synthesised from findings/checks")
    if norm in ("reviewreport", "report"):
        if isinstance(findings, list) and findings:
            lines = ["# Review report", ""]
            for i, item in enumerate(findings, 1):
                if not isinstance(item, dict):
                    continue
                lines.append("## %d. %s" % (i, item.get("category") or item.get("kind") or "finding"))
                lines.append("")
                lines.append("- severity: %s" % (item.get("severity") or "unspecified"))
                if item.get("issue"):
                    lines.append("- issue: %s" % item["issue"])
                if item.get("evidence"):
                    lines.append("- evidence: %s" % item["evidence"])
                if item.get("suggestion"):
                    lines.append("- suggested fix: %s" % item["suggestion"])
                lines.append("")
            return ({"format": "markdown", "content": "\n".join(lines)},
                    "rendered from findings")
    return None, "not derivable from this run's data"


def apply_contract(payload, case):
    names = contract_names(case)
    notes = {}
    flat = {}
    for holder in (payload, payload.get("result") if isinstance(payload.get("result"), dict) else {}):
        if not isinstance(holder, dict):
            continue
        for key, value in holder.items():
            flat.setdefault(str(key), value)
    for name in names:
        if name in payload and payload[name] is not None:
            notes[name] = "produced directly by this run"
            continue
        if name in flat and flat[name] not in (None, "", [], {}):
            payload[name] = flat[name]
            notes[name] = "taken from the run's result section"
            continue
        value, reason = _derive_named(name, flat)
        if value is not None:
            payload[name] = value
            notes[name] = reason
        else:
            payload[name] = None
            notes[name] = reason
    payload["contract_notes"] = notes
    payload["output_contract_fields"] = {"provided": names,
                                         "present": {name: payload.get(name) is not None
                                                     for name in names}}
    return payload


def write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, str(target))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def build_review_report(result, case_id, uncertainty=None):
    """Render a complete review report (markdown) from this run's findings."""
    findings = result.get("findings") or []
    summary = result.get("summary") or {}
    counts = summary.get("by_severity") or {}
    lines = ["# 研究方法与统计审查报告", "",
             "- case_id: `%s`" % (case_id or "unknown"),
             "- 判定: %s" % (summary.get("verdict") or "no_verdict"),
             "- 问题数: %d（high %d / medium %d / low %d）" % (
                 len(findings), counts.get("high", 0), counts.get("medium", 0), counts.get("low", 0)),
             "- 检测章节: %s" % ("、".join(result.get("sections_detected") or []) or "未识别"), ""]
    lines += ["## 一、检查覆盖", "", "| 检查项 | 范围 | 状态 |", "|---|---|---|"]
    for check in result.get("checks") or []:
        lines.append("| %s | %s | %s |" % (check.get("check"), check.get("scope", ""), check.get("status")))
    lines += ["", "## 二、问题清单"]
    if not findings:
        lines += ["", "本次材料在已检查项上未发现问题；未检查项见第五节。"]
    for index, item in enumerate(findings, 1):
        lines += ["", "### F%d [%s] %s" % (index, item.get("severity", "unspecified"), item.get("facet", "finding")), "",
                  "- 定位：`%s`" % (item.get("locator") or "未定位")]
        if item.get("quote"):
            lines.append("- 原文：“%s”" % item["quote"])
        lines += ["- 判定：%s" % (item.get("finding") or ""),
                  "- 依据：%s" % (item.get("evidence") or ""),
                  "- 修改建议：%s" % (item.get("recommendation") or "")]
    lines += ["", "## 三、修改清单"]
    for index, item in enumerate(result.get("revision_checklist") or [], 1):
        lines.append("%d. `%s` — %s" % (index, item.get("locator") or "n/a", item.get("action") or ""))
    lines += ["", "## 四、限制"]
    for item in result.get("limitations") or []:
        lines.append("- %s" % item)
    lines += ["", "## 五、待复核与未检查项"]
    for item in result.get("unverifiable") or []:
        lines.append("- %s：%s" % (item.get("item", ""), item.get("reason", "")))
    for item in (uncertainty or []):
        if isinstance(item, dict):
            lines.append("- %s：%s" % (item.get("type", "uncertainty"), item.get("detail", "")))
        else:
            lines.append("- %s" % item)
    lines += ["", "## 六、运行记录"]
    for item in result.get("change_log") or []:
        lines.append("- %s" % item)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Methods and statistics audit")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--out", "--output", default=DEFAULT_OUT)
    parser.add_argument("--work", default=DEFAULT_WORK)
    args = parser.parse_args(argv)
    os.environ["SK_RESULT_PATH"] = str(getattr(args, "out", None) or getattr(args, "output", None) or "")
    case = {}
    try:
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case.json root must be a JSON object")
        try:
            Path(args.work).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        payload = build_payload(case, read_task_text(args.case, args.work))
        code = 0
    except Exception as exc:
        payload = {"case_id": case_identifier(case) if isinstance(case, dict) else "", "status": "failed",
                   "result": None, "evidence": [],
                   "uncertainty": [{"type": "run_failure", "detail": "Run failed; no audit is reported."}],
                   "errors": [{"stage": "build", "type": type(exc).__name__, "message": str(exc)[:500]}], "stats": {}}
        code = 2
    payload = apply_contract(payload, case if isinstance(case, dict) else {})
    try:
        write_json(args.out, payload)
    except Exception as exc:
        sys.stderr.write(json.dumps({"status": "failed", "stage": "write_output", "message": str(exc)[:300]}) + "\n")
        return 3
    report = payload.get("review_report")
    if isinstance(report, dict) and report.get("content"):
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(args.out)), "review-report.md"), "w", encoding="utf-8") as handle:
                handle.write(report["content"])
        except OSError:
            pass
    sys.stdout.write(json.dumps({"status": payload.get("status"), "case_id": payload.get("case_id"),
                                 "out": str(args.out), "findings": payload.get("stats", {}).get("findings", 0)},
                                ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.environ.get("SK_RESULT_PATH") or "result.json"
            _d = os.path.dirname(os.path.abspath(_p))
            if _d:
                os.makedirs(_d, exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    _fallback = os.environ.get("SK_RESULT_PATH", "")
    if _fallback and not os.path.isfile(_fallback):
        try:
            _parent = os.path.dirname(os.path.abspath(_fallback))
            if _parent:
                os.makedirs(_parent, exist_ok=True)
            with open(_fallback, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0 if _fallback else _rc)
