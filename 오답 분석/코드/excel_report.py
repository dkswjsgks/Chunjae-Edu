"""모델 비교 결과를 엑셀 한 파일로 만든다.

시트
- 오답 판단: 문항별 오답(선지·응답) 1행. 모델별로 '판단'(왜 틀렸는지)과 '근거'(추정 풀이 경로)만 둔다.
- 비용: 모델별 비용 요약 + 문항×모델 비용표.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import analyze_errors as ae

CATEGORY_LABEL = {k: v.split(":", 1)[0] for k, v in ae.ERROR_CATEGORIES.items()}
CONFIDENCE_LABEL = {"low": "낮음", "medium": "보통", "high": "높음"}

HEADER_FILL = PatternFill("solid", fgColor="DDE3EA")
MODEL_FILLS = ["E8F1FB", "EAF6EC", "FDF1E3", "F3EAF7", "FBEAEA", "EEF0F2"]
THIN = Side(style="thin", color="BFC5CC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP_TOP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
BOLD = Font(bold=True)
USD = '"$"#,##0.0000'
USD2 = '"$"#,##0.00'
INT = "#,##0"


def format_tokens(tokens: list, options: dict) -> str:
    parts = []
    for t in tokens:
        if t is None or t == "":
            parts.append("(빈칸)")
        elif t in options and options[t]:
            parts.append(f"{t} {options[t]}")
        else:
            parts.append(str(t))
    return ", ".join(parts)


def judgment_text(a: dict, concepts: dict) -> str:
    lines = [f"[{CATEGORY_LABEL.get(a['error_category'], a['error_category'])}] 신뢰도 {CONFIDENCE_LABEL.get(a['confidence'], a['confidence'])}"]
    names = [concepts.get(c, c) for c in a["concept_ids"]]
    if names:
        lines.append("부족 개념: " + ", ".join(names))
    if a["misconception"]:
        lines.append(a["misconception"])
    return "\n".join(lines)


def _cost(usage: dict, price: dict | None) -> float | None:
    """benchmark_models.cost_usd와 같은 식."""
    if not price:
        return None
    cached = usage.get("cached_input_tokens", 0)
    return ((usage.get("input_tokens", 0) - cached) * price["input"] + cached * price["cached_input"]
            + usage.get("output_tokens", 0) * price["output"]) / 1e6


def _style_header(ws, row: int, n_cols: int) -> None:
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = BOLD
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = BORDER


def judgment_sheet(ws, models, jobs, all_records) -> None:
    keys = [f"{m}:{e}" for m, e in models]
    fixed = ["문항 ID", "지식", "정답", "오답(선지·응답)", "응답 수"]
    n_fixed = len(fixed)

    # 1행: 모델 이름(2칸 병합), 2행: 판단/근거
    for i, h in enumerate(fixed, 1):
        ws.cell(row=1, column=i, value=h)
        ws.merge_cells(start_row=1, start_column=i, end_row=2, end_column=i)
    for mi, (model, effort) in enumerate(models):
        col = n_fixed + 1 + mi * 2
        ws.cell(row=1, column=col, value=f"{model} ({effort or '추론 미지정'})")
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 1)
        ws.cell(row=2, column=col, value="판단")
        ws.cell(row=2, column=col + 1, value="근거")
    n_cols = n_fixed + 2 * len(models)
    _style_header(ws, 1, n_cols)
    _style_header(ws, 2, n_cols)
    for mi in range(len(models)):
        fill = PatternFill("solid", fgColor=MODEL_FILLS[mi % len(MODEL_FILLS)])
        for r in (1, 2):
            for c in (n_fixed + 1 + mi * 2, n_fixed + 2 + mi * 2):
                ws.cell(row=r, column=c).fill = fill

    row = 3
    for j in jobs:
        payload = j["payload"]
        options = {o.get("option_id"): o.get("text", "") for o in payload["question"].get("options", [])}
        answer = " / ".join(format_tokens(v, options) for v in payload["answer_key"]["expected_vectors"]) or payload["source_answer"]
        results = {}
        for k in keys:
            r = all_records.get(k, {}).get(j["item_id"])
            if r and r["status"] == "ok" and r.get("prompt_version") == ae.PROMPT_VERSION:
                results[k] = r["result"]
        first = row
        for p in payload["wrong_patterns"]:
            values = [j["item_id"], payload["taxonomy"].get("지식", ""), answer,
                      format_tokens(p["response_tokens"], options), p["count"]]
            for k in keys:
                res = results.get(k)
                a = next((x for x in res["pattern_analyses"] if x["pattern_id"] == p["pattern_id"]), None) if res else None
                if a:
                    concepts = {c["concept_id"]: c["name"] for c in res["required_concepts"]}
                    values += [judgment_text(a, concepts), a["inferred_solution_path"]]
                else:
                    rec = all_records.get(k, {}).get(j["item_id"])
                    values += [f"(분석 실패: {rec.get('error', '')[:200]})" if rec and rec["status"] != "ok" else "(미실행)", ""]
            for c, v in enumerate(values, 1):
                cell = ws.cell(row=row, column=c, value=v)
                cell.alignment = WRAP_TOP
                cell.border = BORDER
            row += 1
        if row - first > 1:  # 같은 문항의 문항 정보 칸 병합
            for c in range(1, 4):
                ws.merge_cells(start_row=first, start_column=c, end_row=row - 1, end_column=c)

    widths = [11, 18, 16, 20, 7] + [38, 48] * len(models)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=3, column=n_fixed + 1)
    ws.auto_filter.ref = f"A2:{get_column_letter(n_cols)}{max(row - 1, 2)}"


def cost_sheet(ws, models, jobs, all_records, summary_rows, prices, full_items: int) -> None:
    ws.cell(row=1, column=1, value="모델별 비용 요약").font = Font(bold=True, size=13)
    headers = ["모델", "추론 강도", "성공 / 대상", "입력 단가($/1M)", "출력 단가($/1M)",
               "입력 토큰", "캐시 입력 토큰", "출력 토큰(추론 포함)", "추론 토큰",
               "총비용", "문항당 평균", "오답 패턴당 평균", f"전체 {full_items:,}문항 예상", "평균 응답 시간(초)"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=3, column=c, value=h)
    _style_header(ws, 3, len(headers))
    for i, s in enumerate(summary_rows):
        r = 4 + i
        price = prices.get(s["model"], {})
        num = lambda v: v if isinstance(v, (int, float)) else None  # noqa: E731
        values = [s["model"], s["reasoning_effort"] or "미지정", f"{s['items_ok']} / {len(jobs)}",
                  price.get("input"), price.get("output"),
                  s["total_input_tokens"], s["total_cached_input_tokens"], s["total_output_tokens"], s["total_reasoning_tokens"],
                  num(s["total_cost_usd"]), num(s["cost_per_item_usd"]), num(s["cost_per_pattern_usd"]),
                  num(s["est_full_run_usd"]), num(s["latency_mean_sec"])]
        fmts = [None, None, None, USD2, USD2, INT, INT, INT, INT, USD, USD, USD, USD2, "0.0"]
        for c, (v, f) in enumerate(zip(values, fmts), 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = BORDER
            if f:
                cell.number_format = f
    note_row = 5 + len(summary_rows)
    ws.cell(row=note_row, column=1, value=(
        "비용 = (입력 − 캐시 입력)×입력 단가 + 캐시 입력×캐시 단가 + 출력×출력 단가. 검증 실패로 재시도한 호출의 토큰도 포함. "
        f"전체 예상 = 표본 비용 × (전체 {full_items:,}문항 입력량 ÷ 표본 입력량)으로 계산한 근사치. 단가 출처: 코드/model_prices.json"
    )).alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=len(headers))
    ws.row_dimensions[note_row].height = 32

    # 문항 × 모델 비용표
    top = note_row + 2
    ws.cell(row=top, column=1, value="문항별 비용 (USD)").font = Font(bold=True, size=13)
    keys = [f"{m}:{e}" for m, e in models]
    head = ["문항 ID", "오답 패턴 수"] + [m for m, _ in models]
    for c, h in enumerate(head, 1):
        ws.cell(row=top + 1, column=c, value=h)
    _style_header(ws, top + 1, len(head))
    for i, j in enumerate(jobs):
        r = top + 2 + i
        ws.cell(row=r, column=1, value=j["item_id"]).border = BORDER
        ws.cell(row=r, column=2, value=len(j["payload"]["wrong_patterns"])).border = BORDER
        for mi, (k, (model, _)) in enumerate(zip(keys, models)):
            rec = all_records.get(k, {}).get(j["item_id"])
            v = _cost(rec.get("usage", {}), prices.get(model)) if rec else None
            cell = ws.cell(row=r, column=3 + mi, value=v)
            cell.number_format = USD
            cell.border = BORDER
    total_r = top + 2 + len(jobs)
    ws.cell(row=total_r, column=1, value="합계").font = BOLD
    for c in range(2, len(head) + 1):
        col = get_column_letter(c)
        cell = ws.cell(row=total_r, column=c, value=f"=SUM({col}{top + 2}:{col}{total_r - 1})")
        cell.font = BOLD
        cell.number_format = INT if c == 2 else USD
        cell.border = BORDER

    widths = [16, 10, 11, 12, 12, 12, 13, 15, 11, 11, 11, 12, 14, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[3].height = 32


def write_report(path: Path, models, jobs, all_records, summary_rows, prices, full_items: int) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "오답 판단"
    judgment_sheet(ws, models, jobs, all_records)
    cost_sheet(wb.create_sheet("비용"), models, jobs, all_records, summary_rows, prices, full_items)
    wb.save(path)
    return path
