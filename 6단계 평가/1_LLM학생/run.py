"""
[6단계 평가 / 1 LLM 학생 시뮬레이션] 오개념을 가진 LLM 학생과 5단계 튜터를 대화시켜 해결률(Success@k)과 누설률(Telling@k)을 잰다. MathDial 방식.

실행 (레포 루트에서):
  python "6단계 평가/1_LLM학생/run.py" --provider openai
  python "6단계 평가/1_LLM학생/run.py" --provider anthropic --prompt-stage 3

입력: 5단계 2_튜터 설정, 실제 오답 사례(학생 답 + 진단 오개념)
출력: 결과/<실행ID>/ 대화.jsonl, 지표.csv (조건별 Success@5/10, Telling@5/10)
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
    "tutor_conditions": ["A", "B", "baseline_plain", "baseline_next_step"],   # 비교 조건
    "tutor_provider": "openai",          # 튜터 모델 (학생 모델과 분리)
    "max_turns": 10,
    "n_cases": 100,
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

# LLM 출력 형식 (JSON Schema). prompt.md의 지시와 맞춘다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"utterance": {"type": "string"}, "final_answer": {"type": "string"}},
    "required": ["utterance", "final_answer"], "additionalProperties": False,
}

def cases(cfg):
    """
    실제 오답 사례(문항, 학생 답, 확정 Q의 오개념·계산 경로). 학생 ID 없음
    """
    raise NotImplementedError("cases: 아직 구현하지 않았다")


def tutor_turn(condition, case, history, cfg):
    """
    A/B: 5단계 2_튜터의 프롬프트·안전장치로 한 턴
    baseline_plain: 프롬프트 없는 일반 LLM / baseline_next_step: "다음 단계는 뭐야?"만 반복
    """
    raise NotImplementedError("tutor_turn: 아직 구현하지 않았다")


def metrics(dialogues):
    """
    Success@k: k턴 안에 학생 final_answer가 정답
    Telling@k: k턴 안에 튜터가 정답 값을 말함(5단계 safety_check 재사용)
    """
    raise NotImplementedError("metrics: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(CONFIG)
    run = data_io.new_run(HERE, f"6-1-시뮬-{cfg['provider']}", cfg)
    dialogues = []
    for case in cases(cfg):
        for cond in cfg["tutor_conditions"]:
            history = []
            for turn in range(cfg["max_turns"]):
                history.append({"role": "tutor", "text": tutor_turn(cond, case, history, cfg)})
                p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"],
                                           question=case["question"], student_answer=case["student_answer"],
                                           misconception=case["misconception"], trace=case["trace"],
                                           history="\n".join(f"{h['role']}: {h['text']}" for h in history))
                s = llm_client.chat(cfg["provider"], p["system"], p["user"], schema=OUTPUT_SCHEMA,
                                    model=cfg["model"], cache_dir=run.cache, sample=turn)["parsed"]
                history.append({"role": "student", "text": s["utterance"], "final_answer": s["final_answer"]})
            dialogues.append({"case": case["case_id"], "condition": cond, "history": history})
    import json  # noqa: E402
    (run.dir / "대화.jsonl").write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in dialogues), encoding="utf-8")
    metrics(dialogues).to_csv(run.dir / "지표.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
