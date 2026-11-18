"""
[1단계 사전 / 3 KC 묶기] 형식 차이만 있는 KC를 묶는 안을 LLM이 제안하고, 사람이 고친 묶음표를 KC_사전.csv의 kc_group에 반영한다.

실행 (레포 루트에서):
  python "1단계 사전/3_KC_묶기/run.py" --provider openai
  python "1단계 사전/3_KC_묶기/run.py" --provider anthropic --prompt-stage 3

입력: 사전/KC_사전.csv
출력: 결과/<실행ID>/ 묶음안.csv(사람 검토용). --apply <검토한 묶음안.csv> 로 kc_group 반영
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
    "apply": None,                       # 사람이 검토한 묶음안.csv 경로. 주면 LLM을 부르지 않고 반영만 한다
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
                "kc_ids": {"type": "array", "items": {"type": "string"}},
                "reason": {"type": "string"},
            },
            "required": ["group_name", "kc_ids", "reason"], "additionalProperties": False}},
    },
    "required": ["groups"], "additionalProperties": False,
}

def kc_list_text(kc_dict, knowledge_name):
    """
    지식 하나의 KC를 "KC ID | 한국어 이름 | 원문 | 핵심/보조" 줄로 만든다
    """
    raise NotImplementedError("kc_list_text: 아직 구현하지 않았다")


def to_review_sheet(knowledge_name, parsed):
    """
    LLM 묶음안을 행으로: knowledge_name, group_id(KG-<지식약칭>-<번호>), group_name, kc_id, reason, 승인(빈칸)
    묶음에 안 들어간 KC는 자기 자신이 group
    """
    raise NotImplementedError("to_review_sheet: 아직 구현하지 않았다")


def apply_groups(sheet_path):
    """
    승인=1 인 행만 KC_사전.csv의 kc_group에 반영. 나머지는 kc_group = kc_id
    주의: 2_import_eedi_kc_dictionary.py를 다시 실행하면 kc_group이 초기화되므로 이 반영을 다시 한다
    """
    raise NotImplementedError("apply_groups: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(CONFIG)
    if cfg["apply"]:
        apply_groups(cfg["apply"])
        return
    run = data_io.new_run(HERE, "1-3-KC묶기", cfg)
    kc = data_io.load_dictionary("KC_사전")
    rows = []
    for name in cfg["knowledge"]:
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"],
                                   knowledge_name=name, kc_list=kc_list_text(kc, name))
        out = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                              model=cfg["model"], cache_dir=run.cache)
        rows += to_review_sheet(name, out["parsed"])
    import pandas as pd  # noqa: E402
    pd.DataFrame(rows).to_csv(run.dir / "묶음안.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run, note="사람 검토 후 --apply")


if __name__ == "__main__":
    main()
