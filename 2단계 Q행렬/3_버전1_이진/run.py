"""
[2단계 Q행렬 / 3 버전1 이진] 선지마다 KC와 오개념을 "고른다". 고른 것 = 1, 나머지 = 0인 선지×(KC+오개념) Q행렬.

실행 (레포 루트에서):
  python "2단계 Q행렬/3_버전1_이진/run.py" --provider openai
  python "2단계 Q행렬/3_버전1_이진/run.py" --provider anthropic --prompt-stage 3

입력: 선지표.csv, 문항_KC.csv, 사전 KC·오개념·연결표, 문항 입력자료
출력: 결과/<실행ID>/ 매핑.csv(선지별 KC·오개념·계산 경로·검사 결과), Q.csv(0/1), 해당없음.csv
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
    "max_misconceptions": 2,             # 선지 하나에 고를 최대 오개념 수
    "q_rule": "top1",                    # 오개념 열: top1(첫째만 1) | all(고른 것 모두 1)
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "trace": {"type": "string"},
        "kc_ids": {"type": "array", "items": {"type": "string"}},
        "misconception_ids": {"type": "array", "items": {"type": "string"}},
        "none_reason": {"type": "string", "enum": ["", "찍기", "단순 실수", "문제 오독", "사전에 없음"]},
        "new_misconception": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["trace", "kc_ids", "misconception_ids", "none_reason", "new_misconception", "reasoning"],
    "additionalProperties": False,
}

def to_long(mapping, cfg):
    """KC는 고른 것 모두 1, 오개념은 q_rule에 따라 1"""
    out = []
    for r in mapping.itertuples():
        for k in filter(None, r.kc_ids.split(";")):
            out.append((r.option_row_id, k, 1))
        mcs = [m for m in r.misconception_ids.split(";") if m]
        for m in (mcs[:1] if cfg["q_rule"] == "top1" else mcs):
            out.append((r.option_row_id, m, 1))
    return pd.DataFrame(out, columns=["option_row_id", "attribute_id", "value"])


def main():
    cfg = data_io.parse_config(CONFIG)
    run = data_io.new_run(HERE, f"2-v1-{cfg['provider']}-{cfg['kc_size']}-p{cfg['prompt_stage']}", cfg)
    inputs = mc.load_inputs(cfg)
    rows, long = [], []
    for opt in inputs["options"].itertuples():
        kc_lines, kc_ids = mc.kc_candidates(opt.item_id, inputs, cfg)
        mc_lines, mc_ids = mc.misconception_candidates(opt.item_id, kc_ids, inputs, cfg)
        v = dict(mc.item_vars(inputs["packets"][opt.item_id], opt), kc_candidates=kc_lines,
                 misconception_candidates=mc_lines, max_kc=str(cfg["max_kc"]), max_misconceptions=str(cfg["max_misconceptions"]))
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **v)

        out = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                              model=cfg["model"], cache_dir=run.cache)
        r = out["parsed"]
        rows.append({"option_row_id": opt.option_row_id, "item_id": opt.item_id, "is_correct": opt.is_correct,
                     "kc_ids": ";".join(k for k in r["kc_ids"] if k in kc_ids),
                     "misconception_ids": ";".join(m for m in r["misconception_ids"] if m in mc_ids),
                     "trace": r["trace"], "trace_reproduced": mc.reproduces(r["trace"], opt.option_value),
                     "none_reason": r["none_reason"], "new_misconception": r["new_misconception"],
                     "reasoning": r["reasoning"], "model": out["model"]})
    mapping = mc.check_kc_subset(pd.DataFrame(rows))
    mapping.to_csv(run.dir / "매핑.csv", index=False, encoding="utf-8-sig")
    mapping[mapping.none_reason != ""].to_csv(run.dir / "해당없음.csv", index=False, encoding="utf-8-sig")
    mc.to_wide(to_long(mapping, cfg), fill=0).to_csv(run.dir / "Q.csv", encoding="utf-8-sig")
    data_io.finish_run(run, {"none_rate": float((mapping.none_reason != "").mean()),
                             "kc_subset_violation": float((~mapping.kc_subset_ok).mean())},
                       note=f"q_id=Q-v1-{cfg['kc_size']}-p{cfg['prompt_stage']}-{cfg['provider']}")


if __name__ == "__main__":
    main()
