"""
[4단계 프로파일 / 2 학생 진단 카드] 학습 행동 유형을 정하고 조언 입력으로 쓸 학생 진단 카드를 만든다.

실행 (레포 루트에서):  python "4단계 프로파일/2_build_student_card.py"

입력: 1_diagnose_students 결과, 풀이 이력, 추가 데이터 1 KT 확률
출력: 4단계 프로파일/결과/<실행ID>/학생_진단카드.jsonl
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "공통"))

import data_io  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402

# ── 분석 설정. 명령줄 --키 값으로 바꿀 수 있다 ─────────────────────────
PARAMS = {
    "diagnose_run": None,                 # None이면 최신
    "behavior_features": ["실력", "무응답비율", "학습일수", "다시풀기비율"],
    "n_types_range": [2, 6],              # 행동 유형 수 후보 (BIC와 재표집 안정성으로 결정)
    "ability_source": "kt",               # kt(학생×지식 평균 KT 확률) | difficulty_adjusted(난이도 보정 정답률)
}

def behavior_types(attempts, params):
    """
    학생별 특징 → 가우스 혼합 등으로 군집, 유형 수 선택
    """
    raise NotImplementedError("behavior_types: 아직 구현하지 않았다")


def cards(diagnosis_dir, types):
    """
    학생 한 명: 행동 유형, 취약 KC, 반복 오개념(근거 문항·날짜), 한 번 나온 오류, 판단 보류 KC
    학생 ID는 카드 키로만 쓰고 LLM에는 보내지 않는다
    """
    raise NotImplementedError("cards: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    run = data_io.new_run(HERE, "4-2-카드", cfg)
    diag = cfg["diagnose_run"] or data_io.latest_run(HERE, "4-1-진단")
    types = behavior_types(data_io.load_attempts(), cfg)
    import json  # noqa: E402
    with open(run.dir / "학생_진단카드.jsonl", "w", encoding="utf-8") as f:
        for card in cards(diag, types):
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
