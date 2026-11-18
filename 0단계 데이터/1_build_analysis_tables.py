"""
[0단계 데이터 / 1 분석 테이블] 전처리 결과를 파이프라인이 쓰는 테이블 4개로 조인·정리한다. LLM을 쓰지 않는다.

실행 (레포 루트에서):  python "0단계 데이터/1_build_analysis_tables.py"

입력: 데이터 전처리/전처리 결과/ (단원 및 지식_분류표, 토픽과 지식_연결표, 문항 정보_전처리,
      문항별 빈칸_기준정답, 학습자 풀이 이력_전처리, 빈칸별 응답_재채점)
출력: 분석 데이터/ 토픽.csv, 문항.csv, 풀이.csv, 빈칸응답.csv  (열 정의는 분석 데이터/README.md)

전처리 결과 폴더는 고치지 않는다. 여기서 뺀 열(검토·추적용)은 전처리 결과에 그대로 있다.
"""

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "공통"))

import paths  # noqa: E402

TOPIC_COLS = ["topic_id", "topic_name", "knowledge_id", "knowledge_name",
              "major_name", "middle_name", "minor_name", "semester_label"]

ITEM_COLS = [
    # 분류
    "item_id", "semester_label", "major_name", "middle_name", "minor_name",
    "topic_id", "topic_name", "knowledge_id", "knowledge_name",
    "item_form", "difficulty_label", "discrimination_label",
    # 내용
    "question_text", "question_image_description", "option_1", "option_2", "option_3", "option_4", "option_5",
    "explanation_text", "explanation_image_description", "image_path", "image_contains_answer_or_solution",
    # 정답
    "answer_raw", "answer_mode", "answer_expected_count", "answer_expected_vectors",
    "answer_key_source", "answer_key_status", "answer_usable_for_regrading", "answer_key_needs_review", "answer_key_note",
    # 품질
    "needs_content_review", "quality_flags",
]

ATTEMPT_COLS = [
    "attempt_id", "student_id", "test_id", "test_completed_at", "item_order",
    "item_id", "knowledge_id", "topic_id",
    "response_raw", "response_normalized", "response_state", "response_layout_mismatch",
    "source_correctness", "regraded_result", "regraded_correctness", "grading_disagreement",
    "prior_item_attempt_count", "is_repeat_item", "is_first_observed_item",
    "prior_knowledge_attempt_count", "prior_knowledge_distinct_item_count", "analysis_cautions",
]

BLANK_COLS = ["attempt_id", "item_id", "blank_index", "response_token_raw", "response_token_normalized",
              "expected_token", "reference_vector", "matching_mode", "token_origin",
              "positional_alignment_verified", "grading_status"]


def read(name):
    return pd.read_csv(paths.PREPROCESSED / name, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def build_topics():
    onto = read("단원 및 지식_분류표.csv")
    links = read("토픽과 지식_연결표.csv")
    name, parent = dict(zip(onto.node_id, onto.name)), dict(zip(onto.node_id, onto.parent_id))
    rows = []
    for t in links.itertuples():
        minor = parent[t.topic_id]
        middle = parent[minor]
        major = parent[middle]
        semester = parent[major]
        grade = parent[semester]
        rows.append({"topic_id": t.topic_id, "topic_name": name[t.topic_id],
                     "knowledge_id": t.knowledge_id, "knowledge_name": name[t.knowledge_id],
                     "major_name": name[major], "middle_name": name[middle], "minor_name": name[minor],
                     "semester_label": f"{name[grade]}학년 {name[semester]}학기"})
    return pd.DataFrame(rows, columns=TOPIC_COLS).sort_values(["semester_label", "knowledge_name", "topic_name"])


def build_items(topics):
    items = read("문항 정보_전처리.csv")
    keys = read("문항별 빈칸_기준정답.csv").rename(columns={
        "mode": "answer_mode", "expected_count": "answer_expected_count",
        "expected_vectors": "answer_expected_vectors", "source": "answer_key_source",
        "usable_for_regrading": "answer_usable_for_regrading", "needs_key_review": "answer_key_needs_review",
        "note": "answer_key_note"})
    out = items.merge(topics.drop(columns=["knowledge_id", "semester_label"]), on="topic_id", how="left")
    out = out.merge(keys[["item_id", "answer_mode", "answer_expected_count", "answer_expected_vectors",
                          "answer_key_source", "answer_usable_for_regrading", "answer_key_needs_review",
                          "answer_key_note"]], on="item_id", how="left")
    return out[ITEM_COLS].fillna("")


def build_attempts():
    return read("학습자 풀이 이력_전처리.csv")[ATTEMPT_COLS]


def build_blanks():
    return read("빈칸별 응답_재채점.csv")[BLANK_COLS]


def check(topics, items, attempts, blanks):
    assert topics.topic_id.is_unique, "토픽 중복"
    assert items.item_id.is_unique and len(items) == 2197, "문항 수가 전처리 결과와 다름"
    assert attempts.attempt_id.is_unique and len(attempts) == 23409, "풀이 수가 전처리 결과와 다름"
    assert set(attempts.item_id) <= set(items.item_id), "문항 정보에 없는 풀이"
    assert set(blanks.attempt_id) <= set(attempts.attempt_id), "풀이에 없는 빈칸 응답"
    named = items[items.topic_id != ""]
    assert (named.topic_name != "").all(), "토픽 이름을 못 붙인 문항"
    m = items[items.topic_id != ""].merge(topics, on="topic_id", suffixes=("", "_t"))
    assert (m.knowledge_id == m.knowledge_id_t).all() and (m.semester_label == m.semester_label_t).all(), "분류 불일치"


def main():
    topics = build_topics()
    items, attempts, blanks = build_items(topics), build_attempts(), build_blanks()
    check(topics, items, attempts, blanks)
    paths.ANALYSIS_DATA.mkdir(exist_ok=True)
    for name, df in [("토픽", topics), ("문항", items), ("풀이", attempts), ("빈칸응답", blanks)]:
        df.to_csv(paths.ANALYSIS_DATA / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"{name}.csv  {len(df):>6}행 {df.shape[1]:>3}열")


if __name__ == "__main__":
    main()
