"""
[1단계 사전 / 5 missing 군집] 2단계 KC 배정의 문항_누락.csv(모델이 "후보에 없다"고 적은 지식)를 의미별로 묶어
어떤 지식이 반복해서 빠졌는지 보여준다. 새 KC가 필요한지(또는 Eedi에 있는지) 정하는 근거가 된다.

실행 (레포 루트에서):
  python "1단계 사전/5_missing_군집.py" --provider openai --run-dir "2단계 Q행렬/2_문항KC배정/결과/<실행ID>"

입력: <실행 폴더>/문항_누락.csv (item_id, missing)
출력: 1단계 사전/결과/5-missing군집-<날짜>-<번호>/
  - 분해.csv      item_id, need(정리한 필요 지식), kind(지식 / 문항오류 / 사소)
  - 군집.csv      cluster_id, cluster_name, kind, n_items, n_needs, kc_name_proposal, item_ids
  - 군집_문항.csv  item_id, cluster_id (한 문항이 여러 군집에 속할 수 있다)

방법: 1) 문항마다 missing 문장을 "필요 지식" 목록으로 쪼개고 교과서 용어로 정리하며, 문항 자체의 오류 지적과
사소한 지식(KC로 만들 가치가 없는 것)을 표시한다. 2) 정리된 필요 지식 전체를 한 번에 의미별로 묶는다.
LLM 결과이므로 군집 이름과 kind는 사람이 확인한다.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "공통"))

import pandas as pd  # noqa: E402

import data_io  # noqa: E402
import llm_client  # noqa: E402

CONFIG = {
    "provider": "openai",
    "model": None,
    "run_dir": "",                       # 2단계 문항KC배정 결과 폴더(문항_누락.csv가 있는 곳)
    "workers": 8,
}
CACHE_DIR = HERE / "_cache_missing"

SYSTEM = "너는 한국 중학교 1학년 수학(정수와 유리수) 교사다. 문항 풀이에 필요한 지식을 교과서 용어로 정리한다."

SPLIT_USER = """[문항 분석 모델이 적은 메모]
{missing}

위 메모를 "풀이에 필요한 지식" 목록으로 쪼갠다.
- 지식마다 한 가지 기능만 담은 짧은 문장("~하기", "~알기")으로 쓴다. 문항 번호(①, (2) 등)와 특정 수는 빼고 일반화한다.
- 같은 지식은 같은 표현으로 쓴다(예: "양의 정수끼리 대소 비교하기", "부호가 다른 두 유리수의 대소 비교하기").
- kind: 지식 = 학생이 배워야 하는 수학 지식 / 문항오류 = 문항·보기·해설의 오타나 모순을 지적한 것(지식이 아님) / 사소 = 초등 저학년 수준이거나 KC로 만들 가치가 없는 것.
- 메모에 지식과 문항 오류가 같이 있으면 각각 따로 적는다."""

SPLIT_SCHEMA = {
    "type": "object",
    "properties": {"needs": {"type": "array", "items": {
        "type": "object",
        "properties": {"text": {"type": "string"}, "kind": {"type": "string", "enum": ["지식", "문항오류", "사소"]}},
        "required": ["text", "kind"], "additionalProperties": False}}},
    "required": ["needs"], "additionalProperties": False,
}

CLUSTER_USER = """아래는 문항 {n_items}개에서 뽑은 "풀이에 필요한 지식"(kind=지식) 목록이다. 줄 맨 앞은 번호이다.
{needs}

같은 지식(또는 하나의 KC로 가르칠 수 있는 지식)끼리 묶는다.
- 한 군집은 학생에게 한 번에 가르칠 수 있는 하나의 지식 단위여야 한다. 너무 넓게(예: "대소 비교") 묶지 않는다.
- 모든 번호는 정확히 한 군집에 넣는다.
- kc_name_proposal: 이 군집을 KC로 만들 때의 이름(한국어, "~하기" 형태).
- 이름만 다르고 뜻이 같은 것은 합친다."""

CLUSTER_SCHEMA = {
    "type": "object",
    "properties": {"clusters": {"type": "array", "items": {
        "type": "object",
        "properties": {"cluster_name": {"type": "string"}, "kc_name_proposal": {"type": "string"},
                       "need_ids": {"type": "array", "items": {"type": "integer"}}},
        "required": ["cluster_name", "kc_name_proposal", "need_ids"], "additionalProperties": False}}},
    "required": ["clusters"], "additionalProperties": False,
}


def main():
    cfg = data_io.parse_config(CONFIG)
    cfg["workers"] = int(cfg["workers"])
    src = Path(cfg["run_dir"]) / "문항_누락.csv"
    miss = pd.read_csv(src, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    miss = miss[miss.missing.str.strip() != ""]
    run = data_io.new_run(HERE, "5-missing군집", cfg)

    def split(row):
        out = llm_client.chat(cfg["provider"], SYSTEM, SPLIT_USER.format(missing=row.missing), schema=SPLIT_SCHEMA,
                              model=cfg["model"], cache_dir=CACHE_DIR)
        return [{"item_id": row.item_id, "need": n["text"], "kind": n["kind"]} for n in out["parsed"]["needs"]]

    with ThreadPoolExecutor(max_workers=cfg["workers"]) as pool:
        parts = list(pool.map(split, list(miss.itertuples())))
    needs = pd.DataFrame([r for p in parts for r in p])
    needs.to_csv(run.dir / "분해.csv", index=False, encoding="utf-8-sig")

    know = needs[needs.kind == "지식"].reset_index(drop=True)
    lines = "\n".join(f"{i}. {t}" for i, t in enumerate(know.need))
    out = llm_client.chat(cfg["provider"], SYSTEM, CLUSTER_USER.format(n_items=know.item_id.nunique(), needs=lines),
                          schema=CLUSTER_SCHEMA, model=cfg["model"], cache_dir=CACHE_DIR)
    clusters, links = [], []
    seen = set()
    for ci, c in enumerate(out["parsed"]["clusters"], 1):
        ids = [i for i in c["need_ids"] if 0 <= i < len(know) and i not in seen]
        seen.update(ids)
        sub = know.loc[ids]
        clusters.append({"cluster_id": f"M{ci:02d}", "cluster_name": c["cluster_name"], "kc_name_proposal": c["kc_name_proposal"],
                         "n_items": sub.item_id.nunique(), "n_needs": len(sub), "item_ids": ";".join(sorted(set(sub.item_id)))})
        links += [{"item_id": it, "cluster_id": f"M{ci:02d}"} for it in sorted(set(sub.item_id))]
    left = sorted(set(range(len(know))) - seen)
    clu = pd.DataFrame(clusters).sort_values("n_items", ascending=False)
    clu.to_csv(run.dir / "군집.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(links).to_csv(run.dir / "군집_문항.csv", index=False, encoding="utf-8-sig")
    kinds = needs.groupby("kind").item_id.nunique().to_dict()
    print(f"missing 문항 {len(miss)}개 → 필요 지식 {len(needs)}개 (문항 수 기준 {kinds}), 군집 {len(clu)}개, 묶이지 않은 것 {len(left)}개")
    data_io.finish_run(run, {"n_missing_items": len(miss), "n_needs": len(needs), "n_clusters": len(clu), "unclustered": len(left)})


if __name__ == "__main__":
    main()
