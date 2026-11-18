"""
[6단계 평가 / 2 사람 검수] 튜터 발화의 품질(교사 발화 분류)과 수학 정확성을 사람이 검수할 시트를 만들고 집계한다.

실행 (레포 루트에서):  python "6단계 평가/2_review_samples.py"

입력: 1_LLM학생 대화.jsonl, 5단계 조언_샘플.jsonl
출력: 6단계 평가/결과/<실행ID>/발화검수시트.csv, 수학검수시트.csv / (--score) 집계.csv
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
    "dialogue_run": None,
    "n_per_condition": 50,
    "score": None,                        # 채운 시트가 있는 실행 폴더
    "seed": settings.SEED,
}

def move_sheet(dialogues, params):
    """
    발화 표본: 조건을 가리고 Focus/Probing/Telling/Generic 분류 칸(2인)
    """
    raise NotImplementedError("move_sheet: 아직 구현하지 않았다")


def math_sheet(dialogues, params):
    """
    수학 오류 검수 칸 + SymPy 자동 검산 결과(비교용)
    """
    raise NotImplementedError("math_sheet: 아직 구현하지 않았다")


def score_sheets(run_dir):
    """
    조건별 발화 분포, 첫 턴 Telling 비율, κ, 수학 오류율
    """
    raise NotImplementedError("score_sheets: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    if cfg["score"]:
        score_sheets(cfg["score"])
        return
    run = data_io.new_run(HERE, "6-2-검수", cfg)
    dialogues = cfg["dialogue_run"] or data_io.latest_run(paths.STAGE6 / "1_LLM학생", "6-1-시뮬")
    move_sheet(dialogues, cfg).to_csv(run.dir / "발화검수시트.csv", index=False, encoding="utf-8-sig")
    math_sheet(dialogues, cfg).to_csv(run.dir / "수학검수시트.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
