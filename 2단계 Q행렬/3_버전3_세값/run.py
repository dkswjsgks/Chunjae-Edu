"""
[2단계 Q행렬 / 3 버전3 세 값] 선지마다 후보 KC·오개념 각각을 1(이 선지를 고르려면 있어야 함) / 0(없어야 함) / 무관으로 판정한다. 선지×(KC+오개념) 세 값 Q행렬(DiBello 외 2015 방식).

실행 (레포 루트에서):
  python "2단계 Q행렬/3_버전3_세값/run.py" --provider openai
  python "2단계 Q행렬/3_버전3_세값/run.py" --provider anthropic --prompt-stage 3

입력: 선지표.csv, 문항_KC.csv, 사전 KC·오개념·연결표, 문항 입력자료
출력: 결과/<실행ID>/ 코딩.csv(선지별 판정·계산 경로·검사 결과), Q.csv(1 / 0 / 빈칸=무관), 해당없음.csv
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
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "trace": {"type": "string"},
        "codes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "attribute_id": {"type": "string"},
                "value": {"type": "string", "enum": ["1", "0"]},
                "reason": {"type": "string"},
            },
            "required": ["attribute_id", "value", "reason"], "additionalProperties": False}},
        "none_reason": {"type": "string", "enum": ["", "찍기", "단순 실수", "문제 오독", "사전에 없음"]},
        "new_misconception": {"type": "string"},
    },
    "required": ["trace", "codes", "none_reason", "new_misconception"],
    "additionalProperties": False,
}

def kc_ids_with_one(codes):
    """KC 부분집합 검사용: 값이 1인 KC"""
    return ";".join(c["attribute_id"] for c in codes if c["attribute_id"].startswith("KC") and c["value"] == "1")


def main():
    cfg = data_io.parse_config(CONFIG)
    run = data_io.new_run(HERE, f"2-v3-{cfg['provider']}-{cfg['kc_size']}-p{cfg['prompt_stage']}", cfg)
    inputs = mc.load_inputs(cfg)
    rows, long = [], []
    for opt in inputs["options"].itertuples():
        kc_lines, kc_ids = mc.kc_candidates(opt.item_id, inputs, cfg)
        mc_lines, mc_ids = mc.misconception_candidates(opt.item_id, kc_ids, inputs, cfg)
        v = dict(mc.item_vars(inputs["packets"][opt.item_id], opt), kc_candidates=kc_lines,
                 misconception_candidates=mc_lines, max_kc=str(cfg["max_kc"]))
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **v)

        out = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                              model=cfg["model"], cache_dir=run.cache)
        r = out["parsed"]
        codes = [c for c in r["codes"] if c["attribute_id"] in kc_ids + mc_ids]
        rows.append({"option_row_id": opt.option_row_id, "item_id": opt.item_id, "is_correct": opt.is_correct,
                     "kc_ids": kc_ids_with_one(codes), "codes": json.dumps(codes, ensure_ascii=False),
                     "trace": r["trace"], "trace_reproduced": mc.reproduces(r["trace"], opt.option_value),
                     "none_reason": r["none_reason"], "new_misconception": r["new_misconception"], "model": out["model"]})
        long += [{"option_row_id": opt.option_row_id, "attribute_id": c["attribute_id"], "value": int(c["value"])}
                 for c in codes]
    coding = mc.check_kc_subset(pd.DataFrame(rows))
    coding.to_csv(run.dir / "코딩.csv", index=False, encoding="utf-8-sig")
    coding[coding.none_reason != ""].to_csv(run.dir / "해당없음.csv", index=False, encoding="utf-8-sig")
    mc.to_wide(pd.DataFrame(long), fill="").to_csv(run.dir / "Q.csv", encoding="utf-8-sig")
    data_io.finish_run(run, {"none_rate": float((coding.none_reason != "").mean()),
                             "kc_subset_violation": float((~coding.kc_subset_ok).mean())},
                       note=f"q_id=Q-v3-{cfg['kc_size']}-p{cfg['prompt_stage']}-{cfg['provider']}")


if __name__ == "__main__":
    main()
