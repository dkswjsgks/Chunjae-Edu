"""
[2단계 Q행렬 / 3 버전2 확률] 선지마다 먼저 계산 경로를 추론하고, 후보 KC와 후보 오개념 "각각에" 점수를 매긴다. KC는 점수 그대로, 오개념은 상위 N개 점수인 선지×(KC+오개념) Q행렬.

실행 (레포 루트에서):
  python "2단계 Q행렬/3_버전2_확률/run.py" --provider openai
  python "2단계 Q행렬/3_버전2_확률/run.py" --provider anthropic --prompt-stage 3

입력: 선지표.csv, 문항_KC.csv, 사전 KC·오개념·연결표, 문항 입력자료
출력: 결과/<실행ID>/ 추론.csv(선지별 계산 경로), 점수.csv(선지×후보 점수), Q.csv(점수), 해당없음.csv
프롬프트: 같은 폴더 prompt.md
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "공통"))

import data_io  # noqa: E402
import llm_client  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402

sys.path.insert(0, str(HERE.parent))  # mapping_common.py
import json  # noqa: E402

import pandas as pd  # noqa: E402

import mapping_common as mc  # noqa: E402

# ── 실험 설정. 명령줄 --키 값으로 바꿀 수 있다 (예: --provider anthropic --kc-size group) ──────────
CONFIG = {
    "provider": "openai",                # openai | anthropic
    "model": None,                       # None이면 .env의 OPENAI_MODEL / ANTHROPIC_MODEL
    "prompt_file": "prompt.md",
    "prompt_stage": 2,                   # 1 목록만 / 2 +원칙 / 3 +원칙+예시
    "kc_size": "original",               # original(원래 KC) | group(묶은 KC)
    "candidate_scope": "item_kc",        # 오개념 후보: item_kc(문항 KC에 연결된 것) | knowledge(같은 지식 전체)
    "max_kc": 3,                         # 선지 하나에 코딩할 최대 KC 수
    "option_table_run": None,            # 1_build_option_table 실행 ID (None이면 최신)
    "item_kc_run": None,                 # 2_문항KC배정 실행 ID (None이면 최신)
    "top_n": settings.TOP_N_MISCONCEPTIONS,   # 오개념 열: 선지마다 남길 수
    "score_mode": "auto",                # per_candidate(후보마다 Yes/No: GPT 토큰 확률, Claude 샘플링 비율)
                                         # | list(한 번 호출로 후보 전체 확률) | auto(openai→per_candidate, anthropic→list)
    "n_samples": 5,                      # Claude per_candidate 샘플 수
    "normalize": False,                  # True면 오개념 열을 선지 행 합 1로 정규화
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    # 1차 호출: 계산 경로와 해당 없음 판단
    "reason": {
        "type": "object",
        "properties": {
            "trace": {"type": "string"},
            "reasoning": {"type": "string"},
            "none_prob": {"type": "number"},
            "new_misconception": {"type": "string"},
        },
        "required": ["trace", "reasoning", "none_prob", "new_misconception"], "additionalProperties": False,
    },
    # 2차 호출 score_mode=list: 후보 전체 확률
    "list": {
        "type": "object",
        "properties": {
            "kc_scores": {"type": "array", "items": {
                "type": "object", "properties": {"id": {"type": "string"}, "prob": {"type": "number"}},
                "required": ["id", "prob"], "additionalProperties": False}},
            "misconception_scores": {"type": "array", "items": {
                "type": "object", "properties": {"id": {"type": "string"}, "prob": {"type": "number"}},
                "required": ["id", "prob"], "additionalProperties": False}},
        },
        "required": ["kc_scores", "misconception_scores"], "additionalProperties": False,
    },
}

def score_candidates(cfg, v, kc_ids, mc_ids, kc_lines, mc_lines, reason, is_correct, run):
    """후보마다 점수 → ({id: 점수}, score_method). 정답 선지는 오개념 점수를 매기지 않는다(0)."""
    ctx = dict(v, trace=reason["trace"], reasoning=reason["reasoning"])
    if is_correct:
        mc_ids, mc_lines = [], ""
    if cfg["score_mode"] == "list":
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **ctx,
                                   misconception_candidates=mc_lines or "(정답 선지: 오개념 없음)")
        out = llm_client.chat(cfg["provider"], p["system"], p["목록점수"], schema=OUTPUT_SCHEMA["list"],
                              model=cfg["model"], cache_dir=run.cache)["parsed"]
        s = {x["id"]: x["prob"] for x in out["kc_scores"] + out["misconception_scores"] if x["id"] in kc_ids + mc_ids}
        return s, "verbal_list"
    s, method = {}, ""
    lines = dict(l.split(" | ", 1) for l in (kc_lines + "\n" + mc_lines).splitlines() if " | " in l)
    for cid in kc_ids + mc_ids:
        section = "KC판정" if cid in kc_ids else "오개념판정"
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **ctx,
                                   candidate=f"{cid} | {lines.get(cid, '')}")
        r = llm_client.score_yes(cfg["provider"], p["system"], p[section], model=cfg["model"],
                                 n_samples=cfg["n_samples"], cache_dir=run.cache)
        s[cid], method = r["score"], r["score_method"]
    return s, method


def to_long(scores, reasons, cfg):
    """KC 점수는 모두, 오개념 점수는 선지마다 상위 top_n. "해당없음" 열에 none_prob"""
    kc = scores[scores.attribute_id.str.startswith("KC")]
    m = scores[~scores.attribute_id.str.startswith("KC")].sort_values("value", ascending=False)
    m = m.groupby("option_row_id").head(cfg["top_n"])
    if cfg["normalize"]:
        m = m.assign(value=m.value / m.groupby("option_row_id").value.transform("sum"))
    none = reasons[["option_row_id", "none_prob"]].rename(columns={"none_prob": "value"}).assign(attribute_id="해당없음")
    return pd.concat([kc, m, none])[["option_row_id", "attribute_id", "value"]]


def main():
    cfg = data_io.parse_config(CONFIG)
    if cfg["score_mode"] == "auto":
        cfg["score_mode"] = "per_candidate" if cfg["provider"] == "openai" else "list"
    run = data_io.new_run(HERE, f"2-v2-{cfg['provider']}-{cfg['kc_size']}-p{cfg['prompt_stage']}", cfg)
    inputs = mc.load_inputs(cfg)
    rows, long = [], []
    for opt in inputs["options"].itertuples():
        kc_lines, kc_ids = mc.kc_candidates(opt.item_id, inputs, cfg)
        mc_lines, mc_ids = mc.misconception_candidates(opt.item_id, kc_ids, inputs, cfg)
        v = dict(mc.item_vars(inputs["packets"][opt.item_id], opt), kc_candidates=kc_lines,
                 misconception_candidates=mc_lines, max_kc=str(cfg["max_kc"]))
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **v)

        reason = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA["reason"],
                                 model=cfg["model"], cache_dir=run.cache)["parsed"]
        rows.append({"option_row_id": opt.option_row_id, "item_id": opt.item_id, "is_correct": opt.is_correct, **reason,
                     "trace_reproduced": mc.reproduces(reason["trace"], opt.option_value)})
        s, method = score_candidates(cfg, v, kc_ids, mc_ids, kc_lines, mc_lines, reason, str(opt.is_correct) == "1", run)
        long += [{"option_row_id": opt.option_row_id, "attribute_id": k, "value": x, "score_method": method}
                 for k, x in s.items()]
    reasons, scores = pd.DataFrame(rows), pd.DataFrame(long)
    reasons.to_csv(run.dir / "추론.csv", index=False, encoding="utf-8-sig")
    scores.to_csv(run.dir / "점수.csv", index=False, encoding="utf-8-sig")
    reasons[reasons.none_prob >= 0.5].to_csv(run.dir / "해당없음.csv", index=False, encoding="utf-8-sig")
    mc.to_wide(to_long(scores, reasons, cfg), fill=0).to_csv(run.dir / "Q.csv", encoding="utf-8-sig")
    data_io.finish_run(run, note=f"q_id=Q-v2-{cfg['kc_size']}-p{cfg['prompt_stage']}-{cfg['provider']}")


if __name__ == "__main__":
    main()
