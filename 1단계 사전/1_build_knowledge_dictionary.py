"""
[1단계 사전 / 1 지식 사전] 지식 21개의 규모를 정리하고 1차 대상·첫 실험 지식을 표시한다. LLM을 쓰지 않는다.

실행 (레포 루트에서):  python "1단계 사전/1_build_knowledge_dictionary.py"

입력: 분석 데이터/토픽.csv, 문항.csv, 풀이.csv (0단계 데이터/1_build_analysis_tables.py 결과)
출력: 사전/지식.csv

지식에 연결된 토픽 목록은 분석 데이터/토픽.csv, 지식에 연결된 KC는 사전/KC.csv의 knowledge_id로 찾는다.
규모 수치는 제공 샘플 이력 기준이다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "공통"))

import pandas as pd  # noqa: E402

import data_io  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402


def main():
    topics = data_io.load_topics()
    items = data_io.load_items(knowledge=False)
    attempts = data_io.load_attempts(knowledge=False)

    k = topics.groupby(["knowledge_id", "knowledge_name", "semester_label"]).topic_id.nunique() \
        .rename("n_topics").reset_index()
    a = attempts.groupby("knowledge_id").agg(n_attempts=("attempt_id", "size"), n_students=("student_id", "nunique"),
                                             n_wrong=("source_correctness", lambda s: int((s == "N").sum())))
    out = k.merge(items.groupby("knowledge_id").item_id.size().rename("n_items"), on="knowledge_id", how="left") \
        .merge(a, on="knowledge_id", how="left").fillna(0)
    out["is_target"] = out.knowledge_name.isin(settings.TARGET_KNOWLEDGE).astype(int)
    out["is_first_experiment"] = out.knowledge_name.isin(settings.FIRST_EXPERIMENT_KNOWLEDGE).astype(int)
    out = out.astype({c: int for c in ["n_topics", "n_items", "n_attempts", "n_students", "n_wrong"]})
    out = out.sort_values(["is_first_experiment", "is_target", "n_attempts"], ascending=False)

    missing = set(settings.TARGET_KNOWLEDGE) - set(out.knowledge_name)
    if missing:
        raise ValueError(f"분류표에 없는 대상 지식: {missing}")
    paths.DICTIONARY.mkdir(exist_ok=True)
    out.to_csv(paths.DICTIONARY / "지식.csv", index=False, encoding="utf-8-sig")
    print(out[["knowledge_name", "n_items", "n_attempts", "is_target", "is_first_experiment"]].to_string(index=False))


if __name__ == "__main__":
    main()
