"""
[1단계 사전 / 4 오개념 정비] 오개념 사전을 매핑 후보로 쓸 수 있게 LLM 초안 + 사람 검토로 정비한다. 작업은 --task로 고른다.

실행 (레포 루트에서):
  python "1단계 사전/4_오개념_정비/run.py" --provider openai
  python "1단계 사전/4_오개념_정비/run.py" --provider anthropic --prompt-stage 3

입력: 사전/오개념.csv(KC–오개념 연결 하나당 한 행), (task=신규) 2단계 버전별 해당없음.csv
반영: 사전/오개념.csv. 오개념 단위 값(name_ko, category_id, definition, typical_trace, student_explanation 등)은
      그 misconception_id의 모든 행에 같은 값으로 넣는다. 처음 채우는 항목은 열을 새로 만든다
출력: 결과/<실행ID>/ <task>_검토시트.csv(사람 검토용). --apply <검토한 시트> 로 사전에 반영
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
    "task": "검수",                      # 검수(번역·상위분류·기존코드) | 설명문 | 신규(2단계 해당없음 묶기)
    "apply": None,                       # 사람이 검토한 시트 경로. 주면 반영만 한다
    "none_runs": [],                     # task=신규: 2단계 버전 실행 ID들
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    # task마다 다른 형식. prompt.md의 섹션 이름(검수/설명문/신규)과 짝을 이룬다
    "검수": {
        "type": "object",
        "properties": {
            "name_ko": {"type": "string"},
            "translation_ok": {"type": "boolean"},
            "category_id": {"type": "string", "enum": ["CAT-1", "CAT-2", "CAT-3", "CAT-4", "CAT-5"]},
            "our_code": {"type": "string"},
            "relevance": {"type": "string", "enum": ["상", "중", "하"]},
            "note": {"type": "string"},
        },
        "required": ["name_ko", "translation_ok", "category_id", "our_code", "relevance", "note"],
        "additionalProperties": False,
    },
    "설명문": {
        "type": "object",
        "properties": {
            "definition": {"type": "string"},
            "include_examples": {"type": "string"},
            "exclude_examples": {"type": "string"},
            "typical_trace": {"type": "string"},
            "student_explanation": {"type": "string"},
            "teacher_note": {"type": "string"},
        },
        "required": ["definition", "include_examples", "exclude_examples", "typical_trace",
                     "student_explanation", "teacher_note"],
        "additionalProperties": False,
    },
    "신규": {
        "type": "object",
        "properties": {"proposals": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "name_ko": {"type": "string"}, "definition": {"type": "string"},
                "option_row_ids": {"type": "array", "items": {"type": "string"}},
                "typical_trace": {"type": "string"}, "kc_id": {"type": "string"},
            },
            "required": ["name_ko", "definition", "option_row_ids", "typical_trace", "kc_id"],
            "additionalProperties": False}}},
        "required": ["proposals"], "additionalProperties": False,
    },
}

def targets(cfg):
    """
    task=검수/설명문: 매핑 후보 오개념(use_in_mapping=1, 첫 실험 지식) 목록과 프롬프트 변수(dict) 목록
    task=신규: none_runs의 해당없음.csv를 KC별로 모아 한 묶음씩
    """
    raise NotImplementedError("targets: 아직 구현하지 않았다")


def to_sheet_rows(task, target, parsed):
    """
    사람 검토 시트 한 행(원래 값, LLM 제안, 승인 칸)
    """
    raise NotImplementedError("to_sheet_rows: 아직 구현하지 않았다")


def apply_sheet(task, sheet_path):
    """
    승인된 행만 사전/오개념.csv에 반영(reviewed_by, review_note 열 기록)
    task=신규: 승인된 제안을 MC-N<번호>로 사전/오개념.csv에 KC마다 한 행씩 추가(source=오답귀납)
    """
    raise NotImplementedError("apply_sheet: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(CONFIG)
    if cfg["apply"]:
        apply_sheet(cfg["task"], cfg["apply"])
        return
    run = data_io.new_run(HERE, f"1-4-{cfg['task']}", cfg)
    rows = []
    for target, vars in targets(cfg):
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **vars)
        out = llm_client.chat(cfg["provider"], p["system"], p[cfg["task"]], schema=OUTPUT_SCHEMA[cfg["task"]],
                              model=cfg["model"], cache_dir=run.cache)
        rows.append(to_sheet_rows(cfg["task"], target, out["parsed"]))
    import pandas as pd  # noqa: E402
    pd.DataFrame(rows).to_csv(run.dir / f"{cfg['task']}_검토시트.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run, note="사람 검토 후 --apply")


if __name__ == "__main__":
    main()
