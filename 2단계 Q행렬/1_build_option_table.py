"""
[2단계 Q행렬 / 1 선지표] Q행렬의 행(문항-선지)을 만든다. LLM을 쓰지 않는다.

실행 (레포 루트에서):  python "2단계 Q행렬/1_build_option_table.py"

입력: 분석 데이터/문항.csv, 풀이.csv, 빈칸응답.csv
출력: 2단계 Q행렬/결과/<실행ID>/선지표.csv
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "공통"))

import data_io  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402

# ── 분석 설정. 명령줄 --키 값으로 바꿀 수 있다 ─────────────────────────
PARAMS = {
    "min_short_answer_count": settings.MIN_SHORT_ANSWER_COUNT,   # 단답 오답값을 선지 행으로 만들 최소 학생 수
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

CHOICE_FORMS = {"5지 선택"}
LABELS = "①②③④⑤"
UNRESOLVED_KEYS = {"blocked_source_defect", "unresolved"}


def _first(attempts):
    """학생·문항마다 이 자료 안의 첫 응답만. 같은 문항 재풀이는 앞 풀이의 피드백 영향이 있어 세지 않는다"""
    return attempts[attempts.is_first_observed_item == "1"]


def _expected(item):
    """허용 정답 벡터 목록 (JSON 문자열 → list[list[str]])"""
    return json.loads(item.answer_expected_vectors or "[]")


def _row(item, option_type, label, blank, value, correct, n, n_wrong):
    blank_part = f"칸{blank}=" if blank else ""
    return {"option_row_id": f"{item.item_id}:{label or blank_part + value}",
            "item_id": item.item_id, "item_form": item.item_form, "option_type": option_type,
            "option_label": label, "blank_index": blank, "option_value": value,
            "is_correct": "1" if correct else "0", "n_chosen": n,
            "wrong_share": "" if correct or not n_wrong else round(100 * n / n_wrong, 1)}


def choice_rows(items, attempts):
    """
    객관식: 선지마다 한 행 (option_row_id=<item_id>:<선지번호>, option_type=객관식선지/정답, option_value, is_correct, n_chosen)
    선택 학생 0명인 선지도 남긴다
    """
    first = _first(attempts)
    rows = []
    for item in items[items.item_form.isin(CHOICE_FORMS)].itertuples():
        keys = {t for v in _expected(item) for t in v}
        picked = first[(first.item_id == item.item_id) & (first.response_state != "missing")]
        tokens = picked.response_normalized.map(lambda s: set(json.loads(s) or []) - {None})
        n = {lab: picked.student_id[tokens.map(lambda t, lab=lab: lab in t)].nunique() for lab in LABELS}
        n_wrong = picked.student_id[tokens.map(lambda t: bool(t) and not t <= keys)].nunique()
        for k, lab in enumerate(LABELS, 1):
            value = getattr(item, f"option_{k}")
            if value:
                rows.append(_row(item, "정답" if lab in keys else "객관식선지", lab, "", value,
                                 lab in keys, n[lab], n_wrong))
    return rows


def short_answer_rows(items, attempts, blanks, min_count):
    """
    단답: response_normalized 기준 오답값 중 min_count명 이상만 행으로 (option_type=단답오답값)
    나머지는 "<item_id>:기타" 한 행. 여러 칸이면 칸 단위 오답값. 전체 미응답은 행으로 만들지 않는다
    정답도 한 행(option_type=단답정답, option_value=정답 벡터를 ", "로 이음)으로 둔다. 오답 행의 KC 부분집합 검사 기준이다
    """
    first = _first(attempts)
    first = first[first.response_state != "missing"]
    b = blanks[blanks.attempt_id.isin(first.attempt_id) & (blanks.token_origin == "observed")
               & (blanks.response_token_normalized != "")]
    b = b.merge(first[["attempt_id", "student_id"]], on="attempt_id")
    rows = []
    for item in items[~items.item_form.isin(CHOICE_FORMS)].itertuples():
        vectors = _expected(item)
        multi = int(item.answer_expected_count or 1) > 1
        rows.append(_row(item, "단답정답", "", "", ", ".join(vectors[0]) if vectors else "", True,
                         first[(first.item_id == item.item_id) & (first.regraded_correctness == "Y")].student_id.nunique(), 0))
        wrong = b[(b.item_id == item.item_id) & (b.grading_status == "incorrect")]
        n_wrong = wrong.groupby("blank_index").student_id.nunique()   # wrong_share 분모: 그 칸을 틀린 학생 수
        counts = wrong.groupby(["blank_index", "response_token_normalized"]).student_id.nunique()
        rest = 0
        for (blank, value), n in counts.sort_values(ascending=False).items():
            if n >= min_count:
                rows.append(_row(item, "단답오답값", "", blank if multi else "", value, False, n, n_wrong[blank]))
            else:
                rest += n
        if rest:   # 여러 칸이면 n_chosen은 학생 수가 아니라 (칸, 오답값) 건수다
            rows.append(_row(item, "기타", "기타", "", "", False, rest, counts.sum()))
    return rows


def mark_excluded(rows, items):
    """
    기준 정답이 확정되지 않은 문항(blocked_source_defect, unresolved)은 excluded=1
    """
    status = dict(zip(items.item_id, items.answer_key_status))
    for r in rows:
        r["excluded"] = "1" if status.get(r["item_id"]) in UNRESOLVED_KEYS else "0"
    return rows


def main():
    cfg = data_io.parse_config(PARAMS)
    run = data_io.new_run(HERE, "2-1-선지표", cfg)
    items, attempts = data_io.load_items(cfg["knowledge"]), data_io.load_attempts(cfg["knowledge"])
    rows = choice_rows(items, attempts) + short_answer_rows(items, attempts, data_io.load_blank_responses(),
                                                            cfg["min_short_answer_count"])
    import pandas as pd  # noqa: E402
    pd.DataFrame(mark_excluded(rows, items)).to_csv(run.dir / "선지표.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
