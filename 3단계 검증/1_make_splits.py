"""
[3단계 검증 / 1 평가 분할] 모든 Q 후보가 같은 평가 분할을 쓰도록 분할표를 만든다.

실행 (레포 루트에서):  python "3단계 검증/1_make_splits.py"

입력: 분석 데이터/풀이.csv (첫 실험 지식)
출력: 3단계 검증/결과/splits/ (커밋하고 이후 바꾸지 않는다)
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
    "seed": settings.SEED,
    "n_item_folds": 3,                    # 문항 기준 fold 수 (새 문항 예측)
    "item_fold_seeds": 5,                 # 문항 기준 분할 반복 수
    "holdout_last_wrong": 1,              # 오답 선지 예측: 학생별 마지막 오답 몇 개를 평가용으로
    "min_wrong_per_student": 2,           # 오답 선지 예측 대상 학생 최소 오답 수
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

def time_split(attempts, params):
    """
    학생별 마지막 응답 일부를 평가용. 같은 완료일시 응답은 같은 쪽
    """
    raise NotImplementedError("time_split: 아직 구현하지 않았다")


def wrong_option_split(attempts, params):
    """
    오답이 min_wrong_per_student개 이상인 학생의 마지막 오답 holdout_last_wrong개를 평가용
    """
    raise NotImplementedError("wrong_option_split: 아직 구현하지 않았다")


def item_folds(attempts, params):
    """
    문항 기준 n_item_folds-fold를 item_fold_seeds번(seed+i)
    """
    raise NotImplementedError("item_folds: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    out = HERE / "결과" / "splits"
    out.mkdir(parents=True, exist_ok=True)
    attempts = data_io.load_attempts(cfg["knowledge"])
    time_split(attempts, cfg).to_csv(out / "시간기준.csv", index=False, encoding="utf-8-sig")
    wrong_option_split(attempts, cfg).to_csv(out / "오답선지예측.csv", index=False, encoding="utf-8-sig")
    for i, df in enumerate(item_folds(attempts, cfg)):
        df.to_csv(out / f"문항기준_seed{i}.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
