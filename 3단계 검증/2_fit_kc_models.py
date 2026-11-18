"""
[3단계 검증 / 2 KC 사전 검증] KC 배정이 지식=KC, 토픽=KC 기준선보다 학생 정오답을 잘 설명하는지 AFM으로 비교한다.

실행 (레포 루트에서):  python "3단계 검증/2_fit_kc_models.py"

입력: 2단계 2_문항KC배정 결과(원래·묶은 KC), 분석 데이터/문항.csv·풀이.csv, 분할표
출력: 3단계 검증/결과/<실행ID>/kc_비교.csv (AIC, BIC, RMSE, AUC)
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
    "item_kc_runs": [],                   # 비교할 2_문항KC배정 실행 ID들 (원래·묶은 KC, GPT·Claude)
    "baselines": ["knowledge", "topic"],  # 기준선: 지식=KC, 토픽=KC
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

def baseline_q(items, kind):
    """
    문항×KC 0/1 행렬. kind=knowledge면 knowledge_id, topic이면 topic_id를 KC로
    """
    raise NotImplementedError("baseline_q: 아직 구현하지 않았다")


def llm_q(run_id):
    """
    2_문항KC배정 결과 → 문항×KC 0/1 행렬
    """
    raise NotImplementedError("llm_q: 아직 구현하지 않았다")


def fit_afm(attempts, q, split):
    """
    AFM: logit P = 학생 θ + Σ_k q_jk(β_k + γ_k·연습기회_ik). 연습 기회는 완료일시 순 누적
    AIC·BIC(전체 적합), 문항 기준 fold의 새 문항 예측 RMSE·AUC(평균과 신뢰구간)
    """
    raise NotImplementedError("fit_afm: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    run = data_io.new_run(HERE, "3-2-KC검증", cfg)
    attempts, items = data_io.load_attempts(cfg["knowledge"]), data_io.load_items(cfg["knowledge"])
    models = {f"기준선_{b}": baseline_q(items, b) for b in cfg["baselines"]}
    models.update({r: llm_q(r) for r in cfg["item_kc_runs"]})
    import pandas as pd  # noqa: E402
    rows = [{"model": name, **fit_afm(attempts, q, HERE / "결과" / "splits")} for name, q in models.items()]
    pd.DataFrame(rows).to_csv(run.dir / "kc_비교.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
