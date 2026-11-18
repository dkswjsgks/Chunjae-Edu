"""
[3단계 검증 / 3 Q 후보 평가] 모든 Q 후보(버전1·2·3 × KC 크기 × 프롬프트 × LLM)를 같은 예측기·같은 분할·같은 지표로 평가하고 비교표를 만든다.

실행 (레포 루트에서):  python "3단계 검증/3_evaluate_q.py"

입력: 2단계 버전별 Q.csv, 분할표, 풀이 이력, 4_human_review 결과
출력: 3단계 검증/결과/<실행ID>/q후보_비교표.csv, (--confirm) 결과/확정/
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
    "q_runs": [],                         # 비교할 2단계 실행 ID들 (예: 2-v1-openai-original-p2-20261120-01)
    "permutations": 1000,                 # 반복률 순열 검정 횟수
    "bootstrap": 1000,                    # 신뢰구간
    "confirm": None,                      # 확정할 실행 ID. 주면 결과/확정/에 복사
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

def load_q(run_id):
    """
    실행 폴더의 Q.csv → 선지×(KC + 오개념) 가중치 행렬. 버전1 0/1, 버전2 점수, 버전3 1→1, 0·무관→0
    KC 열(KC-로 시작)과 오개념 열을 나눠 돌려준다
    """
    raise NotImplementedError("load_q: 아직 구현하지 않았다")


def wrong_option_prediction(q, attempts, split):
    """
    공통 지표. 학습용 오답으로 학생 오개념 점수 = Σ(고른 선지 행 가중치)
    평가용 오답 문항에서 각 오답 선지 점수 = 그 선지 행 · 학생 점수 → top-1 정확도, 로그우도
    기준선(가장 많이 고른 오답 선지, 무작위)과의 차이
    """
    raise NotImplementedError("wrong_option_prediction: 아직 구현하지 않았다")


def repeat_rate(q, attempts, permutations):
    """
    같은 학생이 다른 문항에서 같은 오개념(상위 1개) 선지를 고른 비율 vs 순열 기대치
    """
    raise NotImplementedError("repeat_rate: 아직 구현하지 않았다")


def agreement(q_runs):
    """
    설정이 같고 LLM·반복만 다른 후보끼리 오개념별 Cohen κ, 선지별 상위 1개 일치율
    """
    raise NotImplementedError("agreement: 아직 구현하지 않았다")


def co_selection_ari(q, attempts):
    """
    학생 공동 선택으로 묶은 오답 선지 군집과 상위 1개 오개념 군집의 ARI
    """
    raise NotImplementedError("co_selection_ari: 아직 구현하지 않았다")


def kc_prediction(q, attempts, split):
    """
    공통 지표. 학습용 응답으로 학생 KC 점수 = Σ(고른 선지 행의 KC 가중치) / 고른 선지 수
    평가용 문항 정오답을 그 문항 정답 선지 KC의 학생 점수로 예측 → AUC, 로그우도
    기준선: 2단계 문항_KC만 쓴 AFM(2_fit_kc_models 결과)
    """
    raise NotImplementedError("kc_prediction: 아직 구현하지 않았다")


def aux_metrics(run_id):
    """
    역산 재현율, 해당 없음 비율, KC 부분집합 위반율, (버전2) MAP@k — 2단계 결과 파일에서
    """
    raise NotImplementedError("aux_metrics: 아직 구현하지 않았다")


def confirm(run_id):
    """
    결과/확정/에 Q.csv, 매핑 파일, 확정_정보.json(q_id, 사전 버전, 날짜) 복사. 선정_기록.md에 한 줄
    """
    raise NotImplementedError("confirm: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    if cfg["confirm"]:
        confirm(cfg["confirm"])
        return
    run = data_io.new_run(HERE, "3-3-Q평가", cfg)
    attempts = data_io.load_attempts(cfg["knowledge"])
    split = HERE / "결과" / "splits" / "오답선지예측.csv"
    rows = []
    for r in cfg["q_runs"]:
        q = load_q(r)
        rows.append({"q_run": r, **wrong_option_prediction(q, attempts, split), **kc_prediction(q, attempts, split),
                     **repeat_rate(q, attempts, cfg["permutations"]), **co_selection_ari(q, attempts), **aux_metrics(r)})
    import pandas as pd  # noqa: E402
    table = pd.DataFrame(rows)
    table.to_csv(run.dir / "q후보_비교표.csv", index=False, encoding="utf-8-sig")
    agreement(cfg["q_runs"]).to_csv(run.dir / "일치도.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
