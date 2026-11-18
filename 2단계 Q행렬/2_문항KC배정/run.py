"""
[2단계 Q행렬 / 2 문항 KC 배정] 문항마다 풀이에 필요한 KC를 사전에서 고른다. Q행렬(세 버전)의 후보 KC와 오개념 후보 범위, 3단계 KC 검증이 쓴다.

실행 (레포 루트에서):
  python "2단계 Q행렬/2_문항KC배정/run.py" --provider openai
  python "2단계 Q행렬/2_문항KC배정/run.py" --provider anthropic --prompt-stage 3

입력: 문항 입력자료(jsonl), 사전/KC_사전.csv, 사전/지식_KC_연결표.csv
출력: 결과/<실행ID>/ 문항_KC.csv (item_id, kc_id, kc_group, steps)
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

# ── 실험 설정. 명령줄 --키 값으로 바꿀 수 있다 (예: --provider anthropic --kc-size group) ──────────
CONFIG = {
    "provider": "openai",                # openai | anthropic
    "model": None,                       # None이면 .env의 OPENAI_MODEL / ANTHROPIC_MODEL
    "prompt_file": "prompt.md",
    "prompt_stage": 2,                   # 1 목록만 / 2 +원칙 / 3 +원칙+예시
    "kc_size": "original",               # original(원래 KC) | group(묶은 KC)
    "kc_roles": ["핵심", "보조"],         # 후보로 줄 KC 구분
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

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

def item_vars(packet):
    """
    문항 입력자료 한 건 → 프롬프트 변수: question(문제+이미지 설명), options("① -3" 줄), answer, explanation
    학생 ID·풀이 이력은 넣지 않는다
    """
    raise NotImplementedError("item_vars: 아직 구현하지 않았다")


def kc_candidates(packet, kc_dict, links, cfg):
    """
    문항 지식의 KC 중 kc_roles에 해당하는 것. kc_size=group이면 묶은 KC 이름으로
    """
    raise NotImplementedError("kc_candidates: 아직 구현하지 않았다")


def to_rows(item_id, parsed):
    """
    단계별 KC를 (item_id, kc_id, step_index, step) 행으로. missing은 따로 모은다
    """
    raise NotImplementedError("to_rows: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(CONFIG)
    run = data_io.new_run(HERE, f"2-2-KC배정-{cfg['provider']}-{cfg['kc_size']}", cfg)
    items = data_io.load_items(cfg["knowledge"])
    packets = data_io.load_item_packets(set(items.item_id))
    kc, links = data_io.load_dictionary("KC_사전"), data_io.load_dictionary("지식_KC_연결표")
    rows = []
    for item_id, packet in packets.items():
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"],
                                   **item_vars(packet), kc_candidates=kc_candidates(packet, kc, links, cfg))
        out = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                              model=cfg["model"], cache_dir=run.cache)
        rows += to_rows(item_id, out["parsed"])
    import pandas as pd  # noqa: E402
    pd.DataFrame(rows).to_csv(run.dir / "문항_KC.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
