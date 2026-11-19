"""
[2단계 Q행렬 / 2 문항 KC 배정] 문항마다 풀이에 필요한 KC를 사전에서 고른다. Q행렬(세 버전)의 후보 KC와 오개념 후보 범위, 3단계 KC 검증이 쓴다.

실행 (레포 루트에서):
  python "2단계 Q행렬/2_문항KC배정/run.py" --provider openai
  python "2단계 Q행렬/2_문항KC배정/run.py" --provider anthropic --prompt-stage 3
  python "2단계 Q행렬/2_문항KC배정/run.py" --provider openai --limit 10      # 시험 실행: 앞 10문항만

입력: 분석 데이터/문항.csv, 문항 입력자료(jsonl), 사전/KC.csv
출력: 결과/<실행ID>/
  문항_KC.csv      item_id, kc_id, kc_group, step_index, step, in_candidates (단계별 KC 한 행. KC 없는 단계는 kc_id 빈칸)
  문항_누락.csv    item_id, missing (풀이에 필요한데 후보에 없다고 모델이 적은 지식. 사전 수정의 근거)
프롬프트: 같은 폴더 prompt.md

후보 KC: 문항의 지식 단위에 속한 KC 중 role이 kc_roles인 것(토픽이 아니라 지식 단위 전체).
같은 설정으로 다시 실행하면 _cache의 응답을 쓰므로 끊긴 실행을 이어서 할 수 있다.
정답 키가 확정되지 않은 문항(blocked_source_defect, unresolved)은 Q행렬에서 빼므로 여기서도 뺀다.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "공통"))

import pandas as pd  # noqa: E402

import data_io  # noqa: E402
import llm_client  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402

# ── 실험 설정. 명령줄 --키 값으로 바꿀 수 있다 (예: --provider anthropic --kc-size group) ──────────
CONFIG = {
    "provider": "openai",                # openai | anthropic
    "model": None,                       # None이면 .env의 OPENAI_MODEL / ANTHROPIC_MODEL
    "prompt_file": "prompt.md",
    "prompt_stage": 2,                   # 1 목록만 / 2 +원칙 / 3 +원칙+예시
    "kc_scope": "experiment",            # knowledge: 문항과 같은 지식 단위의 KC만 / experiment: 첫 실험 지식 전체의 KC(다른 단위 KC도 후보)
    "kc_size": "original",               # original(원래 KC) | group(묶은 KC)
    "kc_roles": ["핵심", "보조"],         # 후보로 줄 KC 구분
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
    "limit": 0,                          # 0이면 전체. 시험 실행용으로 앞에서부터 n문항만
    "workers": 4,                        # 동시 호출 수
}

# 호출 결과 캐시. 실행이 중간에 끊겨도 같은 명령을 다시 실행하면 끝낸 문항은 다시 부르지 않는다.
# 처음부터 다시 받으려면 이 폴더(_cache, git에 올리지 않음)를 지운다.
CACHE_DIR = HERE / "_cache"

EXCLUDED_KEY_STATUS = {"blocked_source_defect", "unresolved"}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "array", "items": {
            "type": "object",
            "properties": {"step": {"type": "string"}, "kc_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["step", "kc_ids"], "additionalProperties": False}},
        "missing": {"type": "string"},
    },
    "required": ["steps", "missing"], "additionalProperties": False,
}


def _with_image(text, image_description):
    text = (text or "").strip()
    image_description = (image_description or "").strip()
    return f"{text}\n[그림 설명] {image_description}" if image_description else text


def item_vars(packet):
    """
    문항 입력자료 한 건 → 프롬프트 변수: question(문제+이미지 설명), options("① -3" 줄), answer, explanation
    학생 ID·풀이 이력은 넣지 않는다(전 기간 응답 분포가 든 historical_outcomes도 쓰지 않는다)
    """
    q = packet["question"]
    options = "\n".join(f"{o['option_id']} {o['text']}" for o in q.get("options") or []) or "(선지 없음: 단답형)"
    answer = packet.get("source_answer") or ""
    if not answer:
        vectors = (packet.get("answer_key") or {}).get("expected_vectors") or []
        answer = " / ".join(", ".join(v) for v in vectors)
    ex = packet.get("explanation") or {}
    return {
        "question": _with_image(q.get("text"), q.get("image_description")),
        "options": options,
        "answer": str(answer),
        "explanation": _with_image(ex.get("text"), ex.get("image_description")) or "(해설 없음)",
    }


def candidate_table(packet, kc_dict, cfg):
    """후보 KC 표: DataFrame(cand_id, cand_name, role). kc_size=group이면 묶음 하나가 후보 하나"""
    kid = packet["taxonomy_ids"]["knowledge_id"]
    ids = set(data_io.knowledge_ids(cfg["knowledge"])) if cfg.get("kc_scope") == "experiment" else {kid}
    sub = kc_dict[kc_dict.knowledge_id.isin(ids) & kc_dict.role.isin(cfg["kc_roles"])]
    if cfg["kc_size"] == "group":
        rank = {r: i for i, r in enumerate(cfg["kc_roles"])}
        sub = sub.assign(_r=sub.role.map(rank)).sort_values("_r").drop_duplicates("kc_group")
        return sub.rename(columns={"kc_group": "cand_id", "kc_group_name": "cand_name"})[["cand_id", "cand_name", "role"]]
    return sub.rename(columns={"kc_id": "cand_id", "kc_name_ko": "cand_name"})[["cand_id", "cand_name", "role"]]


def kc_candidates(packet, kc_dict, cfg):
    """
    사전/KC.csv에서 knowledge_id가 문항 지식과 같고 role이 kc_roles에 있는 KC.
    kc_size=group이면 kc_group, kc_group_name으로 묶어 묶음 하나를 후보 하나로
    → "KC ID | 이름 | 구분" 줄을 이은 문자열
    """
    t = candidate_table(packet, kc_dict, cfg)
    return "\n".join(f"{r.cand_id} | {r.cand_name} | {r.role}" for r in t.itertuples())


def to_rows(item_id, parsed, valid_ids=None):
    """
    단계별 KC를 (item_id, kc_id, step_index, step, in_candidates) 행으로. KC가 없는 단계는 kc_id를 비운다.
    in_candidates: 모델이 후보에 없는 ID를 지어냈는지 표시(valid_ids를 주면 계산).
    missing은 (item_id, missing) 한 줄로 따로 돌려준다.
    """
    rows = []
    for i, s in enumerate(parsed["steps"], 1):
        ids = s["kc_ids"] or [""]
        for k in ids:
            rows.append({"item_id": item_id, "kc_id": k, "step_index": i, "step": s["step"],
                         "in_candidates": "" if valid_ids is None or not k else int(k in valid_ids)})
    return rows, {"item_id": item_id, "missing": (parsed.get("missing") or "").strip()}


def main():
    cfg = data_io.parse_config(CONFIG)
    cfg["limit"], cfg["workers"] = int(cfg["limit"]), int(cfg["workers"])
    run = data_io.new_run(HERE, f"2-2-KC배정-{cfg['provider']}-{cfg['kc_size']}", cfg)
    items = data_io.load_items(cfg["knowledge"])
    items = items[~items.answer_key_status.isin(EXCLUDED_KEY_STATUS)]
    if cfg["limit"]:
        items = items.head(cfg["limit"])
    packets = data_io.load_item_packets(set(items.item_id))
    kc = data_io.load_dictionary("KC")
    kc_group = dict(zip(kc.kc_id, kc.kc_group))

    def one(item_id):
        packet = packets[item_id]
        cands = candidate_table(packet, kc, cfg)
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"],
                                   **item_vars(packet), kc_candidates=kc_candidates(packet, kc, cfg))
        out = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                              model=cfg["model"], cache_dir=CACHE_DIR)
        return to_rows(item_id, out["parsed"], set(cands.cand_id))

    ids = [i for i in items.item_id if i in packets]
    with ThreadPoolExecutor(max_workers=cfg["workers"]) as pool:
        results = list(pool.map(one, ids))
    rows = [r for rs, _ in results for r in rs]
    missing = [m for _, m in results]

    out = pd.DataFrame(rows)
    out.insert(2, "kc_group", [kc_group.get(k, k if str(k).startswith("KG-") else "") for k in out.kc_id])
    out.to_csv(run.dir / "문항_KC.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(missing).to_csv(run.dir / "문항_누락.csv", index=False, encoding="utf-8-sig")
    n_missing = sum(1 for m in missing if m["missing"])
    bad = int((out.in_candidates == 0).sum())
    print(f"문항 {len(ids)}개, KC 행 {len(out)}, 후보 밖 ID {bad}, missing 적힌 문항 {n_missing}")
    data_io.finish_run(run, {"n_items": len(ids), "n_rows": len(out), "n_out_of_candidates": bad,
                             "n_items_with_missing": n_missing})


if __name__ == "__main__":
    main()
