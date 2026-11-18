"""
[3단계 검증 / 4 사람 검수] 선지-오개념 매핑의 블라인드 검수 시트를 만들고, 채운 시트로 정확도를 계산한다.

실행 (레포 루트에서):  python "3단계 검증/4_human_review.py"

입력: 2단계 버전별 매핑 결과
출력: 3단계 검증/결과/<실행ID>/검수시트_검수자A.csv, 검수시트_검수자B.csv / (--score) 검수_정확도.csv
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
    "q_runs": [],
    "per_knowledge": 50,                  # 지식별 표본 선지 수 (선택 학생 많은 오답 선지 위주)
    "reviewers": ["A", "B"],
    "score": None,                        # 채운 시트가 있는 실행 폴더. 주면 정확도·κ 계산
    "seed": settings.SEED,
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

def sample_options(q_runs, params):
    """
    선택 학생 수 가중으로 지식별 per_knowledge개 오답 선지
    """
    raise NotImplementedError("sample_options: 아직 구현하지 않았다")


def blind_sheet(options, q_runs, seed):
    """
    행: 선지 × 후보 오개념(모든 후보의 상위 1개를 섞어 어느 후보에서 왔는지 숨김)
    열: 문항, 학생 답, 오개념 이름·정의, 판정(맞음/부분/틀림/해당없음이 맞음), 메모
    """
    raise NotImplementedError("blind_sheet: 아직 구현하지 않았다")


def score_sheets(run_dir):
    """
    두 검수자 κ, 버전·LLM별 상위 1개 정확도
    """
    raise NotImplementedError("score_sheets: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    if cfg["score"]:
        score_sheets(cfg["score"])
        return
    run = data_io.new_run(HERE, "3-4-사람검수", cfg)
    sheet = blind_sheet(sample_options(cfg["q_runs"], cfg), cfg["q_runs"], cfg["seed"])
    for r in cfg["reviewers"]:
        sheet.drop(columns=["_source"]).to_csv(run.dir / f"검수시트_검수자{r}.csv", index=False, encoding="utf-8-sig")
    sheet.to_csv(run.dir / "_정답키.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
