"""
[5단계 조언 / 1 조언 재료] 방식 A: 오개념마다 미리 써 둘 조언(Focus 질문, 힌트, Telling 문구)을 LLM 초안 + 콘텐츠 담당자 검수로 만든다. 방식 B: 교재 색인(원문을 받으면).

실행 (레포 루트에서):
  python "5단계 조언/1_조언재료/run.py" --provider openai
  python "5단계 조언/1_조언재료/run.py" --provider anthropic --prompt-stage 3

입력: 사전/오개념.csv (학생용 설명문·계산 경로, 1단계 4 --task 설명문이 채운다), (B) 교재 원문 폴더
출력: 결과/<실행ID>/ 사전작성_조언.csv(검수용) / (B) 교재_색인/
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
    "method": "A",                       # A 사전 작성 조언 | B 교재 색인(원문 필요, LLM 안 씀)
    "textbook_dir": None,                # B: 교재 원문 폴더(레포 밖)
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "focus_question": {"type": "string"},
        "probing_question": {"type": "string"},
        "small_hint": {"type": "string"},
        "telling": {"type": "string"},
    },
    "required": ["focus_question", "probing_question", "small_hint", "telling"], "additionalProperties": False,
}

def misconception_vars(row):
    """
    오개념 사전 한 행 → 프롬프트 변수(name_ko, definition, typical_trace, student_explanation, 예시 문항)
    """
    raise NotImplementedError("misconception_vars: 아직 구현하지 않았다")


def build_textbook_index(textbook_dir, out_dir):
    """
    방식 B: 단원·쪽 단위로 나눠 검색 색인. 원문은 커밋하지 않는다
    """
    raise NotImplementedError("build_textbook_index: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(CONFIG)
    run = data_io.new_run(HERE, f"5-1-재료{cfg['method']}", cfg)
    if cfg["method"] == "B":
        build_textbook_index(cfg["textbook_dir"], run.dir / "교재_색인")
        return
    mc = data_io.load_dictionary("오개념").drop_duplicates("misconception_id")
    if "student_explanation" not in mc:
        raise RuntimeError("사전/오개념.csv에 학생용 설명문이 없다. 1단계 4_오개념_정비 --task 설명문을 먼저 반영한다")
    rows = []
    for row in mc[mc.student_explanation != ""].itertuples():
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **misconception_vars(row))
        out = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                              model=cfg["model"], cache_dir=run.cache)
        rows.append({"misconception_id": row.misconception_id, **out["parsed"], "검수": ""})
    import pandas as pd  # noqa: E402
    pd.DataFrame(rows).to_csv(run.dir / "사전작성_조언.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run, note="콘텐츠 담당자 검수 필요")


if __name__ == "__main__":
    main()
