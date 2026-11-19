"""
[3단계 검증 / 1 평가 분할] 모든 Q 후보가 같은 평가 분할을 쓰도록 분할표를 만든다.

실행 (레포 루트에서):  python "3단계 검증/1_make_splits.py"

입력: 분석 데이터/풀이.csv (첫 실험 지식)
출력: 3단계 검증/결과/splits/ (커밋하고 이후 바꾸지 않는다)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

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
    "time_holdout_frac": 0.2,            # 시간 기준: 학생별 마지막 응답 비율
    "holdout_last_wrong": 1,              # 오답 선지 예측: 학생별 마지막 오답 몇 개를 평가용으로
    "min_wrong_per_student": 2,           # 오답 선지 예측 대상 학생 최소 오답 수
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

def answered(attempts):
    """채점 결과가 Y/N인 응답만(무응답·채점불가 제외). 완료일시 순으로 정렬"""
    a = attempts[attempts.regraded_correctness.isin(["Y", "N"])].copy()
    a["t"] = pd.to_datetime(a.test_completed_at)
    return a.sort_values(["student_id", "t", "attempt_id"]).reset_index(drop=True)


def time_split(attempts, params):
    """
    학생별 마지막 응답 일부(time_holdout_frac, 최소 1개)를 평가용. 같은 완료일시 응답은 같은 쪽.
    응답이 1개뿐인 학생은 모두 학습용(평가할 미래가 없다)
    """
    a = answered(attempts)
    rows = []
    for sid, g in a.groupby("student_id", sort=False):
        n = len(g)
        n_hold = max(1, int(round(n * params["time_holdout_frac"]))) if n >= 2 else 0
        times = sorted(g.t.unique(), reverse=True)
        test_times, got = set(), 0
        for k, t in enumerate(times):
            if got >= n_hold or k == len(times) - 1:  # 학습 쪽에 최소 한 시점은 남긴다
                break
            test_times.add(t)
            got += int((g.t == t).sum())
        for aid, t in zip(g.attempt_id, g.t):
            rows.append((aid, sid, "test" if t in test_times else "train"))
    return pd.DataFrame(rows, columns=["attempt_id", "student_id", "split"])


def wrong_option_split(attempts, params):
    """
    오답이 min_wrong_per_student개 이상인 학생의 마지막 오답 holdout_last_wrong개를 평가용(오답 선지 예측용).
    대상이 아닌 학생의 오답은 split을 비워 둔다
    """
    a = answered(attempts)
    w = a[a.regraded_correctness == "N"]
    rows = []
    for sid, g in w.groupby("student_id", sort=False):
        if len(g) < params["min_wrong_per_student"]:
            continue
        k = params["holdout_last_wrong"]
        for j, aid in enumerate(g.attempt_id):
            rows.append((aid, sid, "test" if j >= len(g) - k else "train"))
    return pd.DataFrame(rows, columns=["attempt_id", "student_id", "split"])


def item_folds(attempts, params):
    """
    문항 기준 n_item_folds-fold를 item_fold_seeds번(seed+i). 문항 하나는 한 fold에만 들어간다
    """
    items = np.array(sorted(answered(attempts).item_id.unique()))
    out = []
    for i in range(params["item_fold_seeds"]):
        rng = np.random.RandomState(params["seed"] + i)
        perm = rng.permutation(len(items))
        fold = np.empty(len(items), dtype=int)
        fold[perm] = np.arange(len(items)) % params["n_item_folds"]
        out.append(pd.DataFrame({"item_id": items, "fold": fold}))
    return out


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
