"""
[4단계 프로파일 / 1 학생 진단] 확정 Q로 학생마다 오개념 보유, KC 숙달, 반복 오개념 태그를 정한다.

실행 (레포 루트에서):  python "4단계 프로파일/1_diagnose_students.py"

입력: 3단계 검증/결과/확정/, 풀이 이력, 3단계 반복률
출력: 4단계 프로파일/결과/<실행ID>/학생_오개념.csv, 학생_KC.csv, 반복오개념_태그.csv
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
    "min_items_per_kc": 3,                # 이보다 적게 푼 KC는 진단 보류
    "repeat_min_items": 2,                # 서로 다른 문항 몇 개에서 나와야 반복 태그
    "recency_half_life_days": 30,         # 최근 기록 가중
    "resolve_after_correct": 2,           # 같은 KC 문항을 연달아 몇 개 맞히면 해소
    "as_of": None,                        # 과거 시점 평가: 이 날짜 이전 기록만
}

def misconception_scores(q, attempts, params):
    """
    학생이 고른 오답 선지의 Q 행으로 오개념 점수(최근 가중)
    """
    raise NotImplementedError("misconception_scores: 아직 구현하지 않았다")


def kc_mastery(q_info, attempts, params):
    """
    확정 Q의 KC 열로 숙달 확률: 정답 선지와 오답 선지에서 1인 KC는 쓸 줄 앎, 버전3의 0인 KC는 모름의 근거
    """
    raise NotImplementedError("kc_mastery: 아직 구현하지 않았다")


def repeat_tags(scores, attempts, params):
    """
    반복 태그(근거 문항·날짜), 해소 표시. 기준은 3단계 반복률을 참고해 오개념마다
    """
    raise NotImplementedError("repeat_tags: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    run = data_io.new_run(HERE, "4-1-진단", cfg)
    attempts = data_io.load_attempts()
    q = data_io._csv(paths.STAGE3 / "결과" / "확정" / "Q.csv")
    scores = misconception_scores(q, attempts, cfg)
    scores.to_csv(run.dir / "학생_오개념.csv", index=False, encoding="utf-8-sig")
    kc_mastery(paths.STAGE3 / "결과" / "확정", attempts, cfg).to_csv(run.dir / "학생_KC.csv", index=False, encoding="utf-8-sig")
    repeat_tags(scores, attempts, cfg).to_csv(run.dir / "반복오개념_태그.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
