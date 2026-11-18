"""
[1단계 사전 / 1] (구현·실행 완료)

목적: 전처리 분류표와 이력으로 지식 사전(사전/지식_사전.csv)을 만든다.

입력:
  - 데이터 전처리/전처리 결과/단원 및 지식_분류표.csv, 토픽과 지식_연결표.csv
  - 데이터 전처리/전처리 결과/문항 정보_전처리.csv, 학습자 풀이 이력_전처리.csv

출력:
  - 사전/지식_사전.csv (지식 21개, 1차 대상 5개·첫 실험 2개 표시)

실행 (레포 루트에서):
  python "1단계 사전/1_build_knowledge_dictionary.py"

주의:
  - eedi_subtopic_candidates 열은 비워 둔다. 지식–KC 대응은 2_import_eedi_kc_dictionary.py가 지식_KC_연결표.csv에 만든다.
  - 규모 수치는 제공 샘플 이력 기준이다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "공통"))

import pandas as pd  # noqa: E402

import paths  # noqa: E402
import settings  # noqa: E402


def read(name):
    return pd.read_csv(paths.PREPROCESSED / name, encoding="utf-8-sig", dtype=str)


def main():
    onto = read("단원 및 지식_분류표.csv")
    topic_knowledge = read("토픽과 지식_연결표.csv")
    items = read("문항 정보_전처리.csv")
    attempts = read("학습자 풀이 이력_전처리.csv")

    name = dict(zip(onto.node_id, onto.name))
    parent = dict(zip(onto.node_id, onto.parent_id))
    knowledge = onto[onto.node_type == "knowledge"]

    rows = []
    for kid, kname in zip(knowledge.node_id, knowledge.name):
        topics = topic_knowledge.loc[topic_knowledge.knowledge_id == kid, "topic_id"].tolist()
        a = attempts[attempts.knowledge_id == kid]
        semester = parent.get(kid)
        grade = parent.get(semester)
        rows.append({
            "knowledge_id": kid,
            "knowledge_name": kname,
            "grade_semester": f"{name.get(grade, '')} {name.get(semester, '')}".strip(),
            "topic_ids": ";".join(topics),
            "topic_names": ";".join(name.get(t, "") for t in topics),
            "n_items": int((items.knowledge_id == kid).sum()),
            "n_attempts": len(a),
            "n_students": a.student_id.nunique(),
            "n_wrong": int((a.source_correctness == "N").sum()),
            "is_target": int(kname in settings.TARGET_KNOWLEDGE),
            "is_first_experiment": int(kname in settings.FIRST_EXPERIMENT_KNOWLEDGE),
            "eedi_subtopic_candidates": "",
        })

    out = pd.DataFrame(rows).sort_values(["is_first_experiment", "is_target", "n_attempts"], ascending=False)
    missing = set(settings.TARGET_KNOWLEDGE) - set(out.knowledge_name)
    if missing:
        raise ValueError(f"분류표에 없는 대상 지식: {missing}")
    paths.DICTIONARY.mkdir(exist_ok=True)
    out.to_csv(paths.DICTIONARY / "지식_사전.csv", index=False, encoding="utf-8-sig")
    print(out[["knowledge_name", "n_items", "n_attempts", "is_target", "is_first_experiment"]].to_string(index=False))


if __name__ == "__main__":
    main()
