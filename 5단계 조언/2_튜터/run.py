"""
[5단계 조언 / 2 튜터] 학생 진단 카드와 확정 Q로 첫 조언(또는 대화 한 턴)을 만든다. 방식 A/B는 재료만 다르고 정책·안전장치는 같다.

실행 (레포 루트에서):
  python "5단계 조언/2_튜터/run.py" --provider openai
  python "5단계 조언/2_튜터/run.py" --provider anthropic --prompt-stage 3

입력: 확정 Q, 학생 진단 카드, 문항 입력자료, 1_조언재료 결과, (B) 교재 색인
출력: 결과/<실행ID>/ 조언_샘플.jsonl (방식, 턴, 발화, 안전검사 결과)
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
    "method": "A",                       # A 사전 작성 조언 | B RAG
    "max_turns": 4,                      # 이 턴을 넘으면 Telling
    "materials_run": None,               # 1_조언재료 실행 ID (None이면 최신)
    "card_run": None,                    # 4단계 카드 실행 ID (None이면 최신)
    "sample_cases": 50,                  # 평가용으로 만들 (학생, 오답) 사례 수
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "move": {"type": "string", "enum": ["Focus", "Probing", "Hint", "Telling", "Close"]},
        "utterance": {"type": "string"},
    },
    "required": ["move", "utterance"], "additionalProperties": False,
}

def cases(cfg):
    """
    평가용 (학생 카드, 문항, 학생 답) 사례. 학생 ID는 LLM 입력에서 뺀다
    """
    raise NotImplementedError("cases: 아직 구현하지 않았다")


def tutor_vars(case, cfg):
    """
    max_turns, 문항·정답·해설·학생 답, 진단된 오개념과 계산 경로(확정 Q 조회), 진단 카드 요약,
    방식 A: 사전 작성 조언 / 방식 B: 교재 검색 결과(쪽수), 대화 기록, 현재 턴
    """
    raise NotImplementedError("tutor_vars: 아직 구현하지 않았다")


def safety_check(utterance, case):
    """
    정답 누설 검사(약분 전후·소수·선지 번호·부등호 표현), SymPy 검산
    실패하면 (ok=False, 이유). run.py가 한 번 재생성 후 고정 문구로 대체
    """
    raise NotImplementedError("safety_check: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(CONFIG)
    run = data_io.new_run(HERE, f"5-2-튜터{cfg['method']}-{cfg['provider']}", cfg)
    import json  # noqa: E402
    with open(run.dir / "조언_샘플.jsonl", "w", encoding="utf-8") as f:
        for case in cases(cfg):
            p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **tutor_vars(case, cfg))
            out = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                                  model=cfg["model"], cache_dir=run.cache)["parsed"]
            ok, why = safety_check(out["utterance"], case)
            f.write(json.dumps({"case": case["case_id"], **out, "safe": ok, "safety_note": why},
                               ensure_ascii=False) + "\n")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
