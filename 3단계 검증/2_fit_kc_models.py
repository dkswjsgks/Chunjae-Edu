"""
[3단계 검증 / 2 KC 사전 검증] KC 배정이 지식=KC, 토픽=KC 기준선보다 학생 정오답을 잘 설명하는지 AFM으로 비교한다.

실행 (레포 루트에서):  python "3단계 검증/2_fit_kc_models.py" --item-kc-runs <2_문항KC배정 실행 ID들>

입력: 2단계 2_문항KC배정 결과(원래·묶은 KC), 분석 데이터/문항.csv·풀이.csv, 분할표
출력: 3단계 검증/결과/<실행ID>/
  kc_비교.csv        모델별 AIC, BIC, 새 문항 예측 RMSE·AUC·로그손실(기준선 대비 차이와 95% 구간), 시간 기준 평가
  자체KC_기여.csv    자체 KC(KC-N*)를 하나씩 뺐을 때 새 문항 예측이 얼마나 나빠지는가
  config.json

한계: AFM은 "이 KC 묶음이 정오답 패턴을 설명하는가"만 본다. 라벨이 문항 내용과 맞는지(정확도)는
사람 검수(4_human_review.py)로만 확인한다. 문항 KC는 학생 응답을 보지 않고 배정했으므로 평가 누수는 없다.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "공통"))

import data_io  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402

# ── 분석 설정. 명령줄 --키 값으로 바꿀 수 있다 ─────────────────────────
PARAMS = {
    "item_kc_runs": [],                   # 비교할 2_문항KC배정 실행 ID들 (원래·묶은 KC, GPT·Claude)
    "baselines": ["knowledge", "topic"],  # 기준선: 지식=KC, 토픽=KC
    "reference": "기준선_topic",          # 차이를 재는 기준 모델
    "ablation_run": "",                   # 자체 KC 제거·무작위 섞기 대조를 돌릴 실행 ID(비우면 마지막 실행)
    "n_shuffle": 5,                       # 무작위 섞기 반복 수
    "n_boot": 500,                        # 문항 부트스트랩 반복 수
    "reg_c": 1.0,                         # 로지스틱 L2 강도(작을수록 강함). 모든 모델에 같은 값
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

SPLITS = HERE / "결과" / "splits"


# ---------------------------------------------------------------- Q 만들기
def baseline_q(items, kind):
    """
    문항×KC 0/1 행렬. kind=knowledge면 knowledge_id, topic이면 topic_id를 KC로
    """
    col = {"knowledge": "knowledge_id", "topic": "topic_id"}[kind]
    it = items[items[col] != ""]
    return pd.crosstab(it.item_id, it[col]).clip(upper=1).astype(int)


def llm_q(run_id, group=False):
    """
    2_문항KC배정 결과 → 문항×KC 0/1 행렬. group=True면 묶음 KC(kc_group) 단위
    """
    d = paths.REPO / "2단계 Q행렬" / "2_문항KC배정" / "결과" / run_id
    k = pd.read_csv(d / "문항_KC.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    k = k[k.kc_id != ""]
    col = "kc_group" if group else "kc_id"
    k = k[k[col] != ""]
    return pd.crosstab(k.item_id, k[col]).clip(upper=1).astype(int)


# ---------------------------------------------------------------- AFM
def prep(attempts):
    a = attempts[attempts.regraded_correctness.isin(["Y", "N"])].copy()
    a["y"] = (a.regraded_correctness == "Y").astype(int)
    a["t"] = pd.to_datetime(a.test_completed_at)
    return a.sort_values(["student_id", "t", "attempt_id"]).reset_index(drop=True)


def attempt_matrices(a, q):
    """응답×KC 행렬 Qa와 연습 기회 Opp(그 학생이 더 이른 시각에 푼, 같은 KC가 붙은 응답 수)"""
    Qa = q.reindex(a.item_id).fillna(0).to_numpy(dtype=float)
    opp = np.zeros_like(Qa)
    sid = a.student_id.to_numpy()
    t = a.t.to_numpy()
    start = 0
    n = len(a)
    for end in range(1, n + 1):
        if end == n or sid[end] != sid[start]:
            cum = np.zeros(Qa.shape[1])
            i = start
            while i < end:
                j = i
                while j < end and t[j] == t[i]:
                    j += 1
                opp[i:j] = cum          # 같은 완료일시 응답끼리는 서로의 기회가 아니다
                cum = cum + Qa[i:j].sum(axis=0)
                i = j
            start = end
    return Qa, opp


def design(a, Qa, opp, stu_index):
    n = len(a)
    rows = np.arange(n)
    cols = a.student_id.map(stu_index).to_numpy()
    S = sparse.csr_matrix((np.ones(n), (rows, cols)), shape=(n, len(stu_index)))
    return sparse.hstack([S, sparse.csr_matrix(Qa), sparse.csr_matrix(np.log1p(opp) * Qa)]).tocsr()


def _fit(X, y, c):
    m = LogisticRegression(C=c, max_iter=300, solver="lbfgs")
    m.fit(X, y)
    return m


def _metrics(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {"rmse": float(np.sqrt(np.mean((y - p) ** 2))),
            "auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else np.nan,
            "logloss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))}


def fit_afm(attempts, q, split, c=1.0):
    """
    AFM: logit P = 학생 θ + Σ_k q_jk(β_k + γ_k·연습기회_ik). 연습 기회는 완료일시 순 누적(γ는 log(1+기회)에 곱함)
    AIC·BIC(전체 적합), 문항 기준 fold의 새 문항 예측 RMSE·AUC(평균과 신뢰구간)
    돌려주는 값: 요약 dict + 문항 기준 평가용 응답별 예측(oof, 시드 평균)과 시간 기준 예측
    """
    a = prep(attempts)
    q = q.loc[:, (q.reindex(a.item_id.unique()).fillna(0).sum() > 0).values]  # 이 데이터에 한 번도 안 나온 KC 열 제거
    stu_index = {s: i for i, s in enumerate(a.student_id.unique())}
    Qa, opp = attempt_matrices(a, q)
    X = design(a, Qa, opp, stu_index)
    y = a.y.to_numpy()

    # 전체 적합 AIC·BIC (벌점 적합이므로 근사값. 학생 모수는 모든 모델에 같다)
    m = _fit(X, y, c)
    p = np.clip(m.predict_proba(X)[:, 1], 1e-9, 1 - 1e-9)
    ll = float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))
    k = 1 + len(stu_index) + 2 * q.shape[1]
    out = {"n_kc": q.shape[1], "items_with_kc": int((q.reindex(a.item_id.unique()).fillna(0).sum(axis=1) > 0).sum()),
           "n_items": a.item_id.nunique(), "n_attempts": len(a), "loglik": ll,
           "aic": 2 * k - 2 * ll, "bic": k * np.log(len(a)) - 2 * ll}

    # 문항 기준 fold: 새 문항 예측
    seeds = sorted(SPLITS.glob("문항기준_seed*.csv"))
    oof = np.zeros((len(seeds), len(a)))
    per_seed = []
    for si, f in enumerate(seeds):
        fold = pd.read_csv(f, dtype={"item_id": str}).set_index("item_id").fold
        af = a.item_id.map(fold).to_numpy()
        for fo in sorted(set(fold)):
            tr, te = af != fo, af == fo
            mm = _fit(X[tr], y[tr], c)
            oof[si, te] = mm.predict_proba(X[te])[:, 1]
        per_seed.append(_metrics(y, oof[si]))
    ps = pd.DataFrame(per_seed)
    for col in ["rmse", "auc", "logloss"]:
        out[f"item_{col}"] = float(ps[col].mean())
        out[f"item_{col}_sd_seed"] = float(ps[col].std(ddof=1)) if len(ps) > 1 else np.nan

    # 시간 기준: 마지막 응답 일부 예측
    ts = pd.read_csv(SPLITS / "시간기준.csv", dtype=str).set_index("attempt_id").split
    sp = a.attempt_id.map(ts).to_numpy()
    tr, te = sp == "train", sp == "test"
    mt = _fit(X[tr], y[tr], c)
    pt = mt.predict_proba(X[te])[:, 1]
    out.update({f"time_{k_}": v for k_, v in _metrics(y[te], pt).items()})

    # 계수 요약(KC별 β, γ) - 해석용
    K = q.shape[1]
    coef = m.coef_[0]
    beta = pd.Series(coef[len(stu_index):len(stu_index) + K], index=q.columns)
    gamma = pd.Series(coef[len(stu_index) + K:], index=q.columns)
    return out, {"y": y, "oof": oof.mean(axis=0), "item": a.item_id.to_numpy(), "beta": beta, "gamma": gamma}


def boot_diff(pred_a, pred_b, n_boot, seed=0):
    """문항을 다시 뽑는 부트스트랩으로 모델 a - 모델 b의 RMSE·AUC·로그손실 차이와 95% 구간"""
    y, item = pred_a["y"], pred_a["item"]
    uniq, inv = np.unique(item, return_inverse=True)
    idx_by_item = [np.where(inv == i)[0] for i in range(len(uniq))]
    rng = np.random.RandomState(seed)
    res = {"rmse": [], "auc": [], "logloss": []}
    for _ in range(n_boot):
        pick = rng.randint(0, len(uniq), len(uniq))
        ix = np.concatenate([idx_by_item[i] for i in pick])
        if len(set(y[ix])) < 2:
            continue
        ma, mb = _metrics(y[ix], pred_a["oof"][ix]), _metrics(y[ix], pred_b["oof"][ix])
        for k in res:
            res[k].append(ma[k] - mb[k])
    return {k: (float(np.mean(v)), float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) for k, v in res.items()}


def main():
    cfg = data_io.parse_config(PARAMS)
    run = data_io.new_run(HERE, "3-2-KC검증", cfg)
    attempts, items = data_io.load_attempts(cfg["knowledge"]), data_io.load_items(cfg["knowledge"])
    c = float(cfg["reg_c"])

    models = {f"기준선_{b}": baseline_q(items, b) for b in cfg["baselines"]}
    models["기준선_학생만"] = pd.DataFrame(index=items.item_id)  # KC 없이 학생 효과만
    for r in cfg["item_kc_runs"]:
        tag = r.split("-")[-1] if r.startswith("2-2-") else r
        models[f"{tag}|원래"] = llm_q(r)
        models[f"{tag}|묶음"] = llm_q(r, group=True)

    # 자체 KC 제거·무작위 섞기 대조 (마지막 실행 기준)
    abl = cfg["ablation_run"] or (cfg["item_kc_runs"][-1] if cfg["item_kc_runs"] else "")
    if abl:
        qa = llm_q(abl)
        own = [k for k in qa.columns if k.startswith("KC-N")]
        models["대조|자체KC제거"] = qa.drop(columns=own)
        for s in range(int(cfg["n_shuffle"])):
            rng = np.random.RandomState(1000 + s)
            sh = qa.copy()
            sh.index = rng.permutation(qa.index.to_numpy())  # 문항에 붙은 KC 묶음을 다른 문항과 맞바꿈
            models[f"대조|무작위섞기{s + 1}"] = sh

    rows, preds, betas = [], {}, {}
    for name, q in models.items():
        res, pr = fit_afm(attempts, q, SPLITS, c)
        rows.append({"model": name, **res})
        preds[name], betas[name] = pr, (pr["beta"], pr["gamma"])
        print(name, {k: round(v, 4) for k, v in res.items() if isinstance(v, float)}, flush=True)

    ref = cfg["reference"]
    df = pd.DataFrame(rows)
    for i, r in df.iterrows():
        if r.model == ref or ref not in preds:
            continue
        d = boot_diff(preds[r.model], preds[ref], int(cfg["n_boot"]))
        for k in ["rmse", "auc", "logloss"]:
            df.loc[i, f"d_{k}_vs_ref"] = d[k][0]
            df.loc[i, f"d_{k}_lo"] = d[k][1]
            df.loc[i, f"d_{k}_hi"] = d[k][2]
    df.to_csv(run.dir / "kc_비교.csv", index=False, encoding="utf-8-sig")

    # 무작위 섞기 요약
    sh = df[df.model.str.startswith("대조|무작위섞기")]
    if len(sh):
        print("무작위섞기 평균 item_rmse", sh.item_rmse.mean(), "auc", sh.item_auc.mean(), "logloss", sh.item_logloss.mean())

    # 자체 KC 하나씩 뺀 기여도
    if abl:
        qa = llm_q(abl)
        _, pfull = fit_afm(attempts, qa, SPLITS, c)
        a = prep(attempts)
        rows2 = []
        for kc in [k for k in qa.columns if k.startswith("KC-N")]:
            r2, p2 = fit_afm(attempts, qa.drop(columns=[kc]), SPLITS, c)
            d = boot_diff(p2, pfull, int(cfg["n_boot"]))  # (뺀 모델) - (전체)
            n_it = int(qa[kc].sum())
            n_at = int(a.item_id.isin(qa.index[qa[kc] > 0]).sum())
            rows2.append({"kc_id": kc, "n_items": n_it, "n_attempts": n_at,
                          "d_logloss_if_removed": d["logloss"][0], "lo": d["logloss"][1], "hi": d["logloss"][2],
                          "d_rmse_if_removed": d["rmse"][0], "d_auc_if_removed": d["auc"][0],
                          "beta": float(pfull["beta"].get(kc, np.nan)), "gamma": float(pfull["gamma"].get(kc, np.nan))})
            print(rows2[-1], flush=True)
        pd.DataFrame(rows2).to_csv(run.dir / "자체KC_기여.csv", index=False, encoding="utf-8-sig")

    data_io.finish_run(run, metrics={"ref": ref, "n_models": len(df)}, note="AFM KC 검증")
    print("done", run.dir)


if __name__ == "__main__":
    main()
