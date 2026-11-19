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
    "subtopics": ["Mixed operation Negative Numbers", "Absolute Values and Opposites"],  # 샘플 단위(Eedi 소주제). 가장 작은 범위부터
    "limit": 0,                          # 0이면 전부, 아니면 앞에서 이만큼만(시험용)
    "workers": 4,
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

CACHE_DIR = HERE / "_cache"
REL_RANK = {"상": 3, "중": 2, "하": 1}
SHEET_COLS = {
    "검수": ["misconception_id", "name_en", "name_ko_원래", "name_ko_제안", "translation_ok", "category_id", "our_code_원래",
            "our_code_제안", "relevance_원래", "relevance_제안", "note", "승인", "검토자", "검토메모"],
    "설명문": ["misconception_id", "name_ko", "definition", "include_examples", "exclude_examples", "typical_trace",
            "student_explanation", "teacher_note", "승인", "검토자", "검토메모"],
}


def _subtopic_links(cfg):
    """사전/오개념.csv 연결 행 중 매핑 후보(use_in_mapping=1)이고 KC가 cfg['subtopics']의 Eedi 소주제에 속한 것"""
    mc, kc = data_io.load_dictionary("오개념"), data_io.load_dictionary("KC")
    sub = kc[kc.eedi_subtopic.isin(cfg["subtopics"])]
    return mc[(mc.use_in_mapping == "1") & mc.kc_id.isin(sub.kc_id)].merge(
        kc[["kc_id", "kc_name_ko", "knowledge_name"]], on="kc_id", how="left")


def _our_codes(mc):
    """기존 오류 코드 초안과 그 코드가 붙은 오개념 이름 하나씩 → 프롬프트용 문자열"""
    d = mc[mc.our_code_draft != ""].drop_duplicates("our_code_draft")
    return "\n".join(f"{r.our_code_draft} | {r.name_ko or r.name_en}" for r in d.itertuples())


def targets(cfg):
    """
    task=검수/설명문: 매핑 후보 오개념(use_in_mapping=1)이면서 연결 KC가 cfg["subtopics"] 소주제에 속하는 것의
      (오개념 한 줄, 프롬프트 변수 dict) 목록. 오개념 하나는 한 번만 부른다. cfg["limit"]이 0이 아니면 앞에서 그만큼만.
    task=신규: 2단계 선지 매핑의 해당없음 결과가 있어야 해서 아직 못 한다
    """
    if cfg["task"] == "신규":
        raise NotImplementedError("task=신규는 2단계 선지 매핑의 해당없음.csv가 생긴 뒤에 구현한다")
    links = _subtopic_links(cfg)
    all_mc = data_io.load_dictionary("오개념")
    codes = _our_codes(all_mc)
    out = []
    for mid, g in links.groupby("misconception_id", sort=False):
        first = g.iloc[0]
        rel = max(g.relevance, key=lambda r: REL_RANK.get(r, 0))
        base = {"misconception_id": mid, "name_en": first.name_en, "name_ko": first.name_ko,
                "relevance": rel, "our_codes": codes, "kc_names": "; ".join(sorted(set(g.kc_name_ko))),
                "knowledge_name": first.knowledge_name, "our_code_draft": first.our_code_draft,
                # 2단계 선지 매핑이 아직 없어 실제 선지 예시를 못 넣는다
                "examples": "(2단계 선지 매핑 전이라 실제 선지 예시 없음. 원문 이름만으로 설명한다)"}
        out.append((base, base))
    limit = int(cfg.get("limit") or 0)
    return out[:limit] if limit else out


def to_sheet_rows(task, target, parsed):
    """
    사람 검토 시트 한 행(원래 값, LLM 제안, 승인 칸). 승인·검토자·검토메모는 사람이 채운다
    """
    t = target
    if task == "검수":
        return {"misconception_id": t["misconception_id"], "name_en": t["name_en"], "name_ko_원래": t["name_ko"],
                "name_ko_제안": parsed["name_ko"], "translation_ok": parsed["translation_ok"],
                "category_id": parsed["category_id"], "our_code_원래": t["our_code_draft"], "our_code_제안": parsed["our_code"],
                "relevance_원래": t["relevance"], "relevance_제안": parsed["relevance"], "note": parsed["note"],
                "승인": "", "검토자": "", "검토메모": ""}
    return {"misconception_id": t["misconception_id"], "name_ko": t["name_ko"], **{k: parsed[k] for k in (
        "definition", "include_examples", "exclude_examples", "typical_trace", "student_explanation", "teacher_note")},
            "승인": "", "검토자": "", "검토메모": ""}


def apply_sheet(task, sheet_path):
    """
    승인된 행(승인 칸이 O이고 검토자가 적힌 행)만 사전/오개념.csv에 반영(reviewed_by, review_note 열 기록).
    오개념 단위 값이라 그 misconception_id의 모든 행에 같은 값을 넣는다. 검수는 name_ko, category_id, our_code를 반영한다
    (관련도 제안은 연결 KC마다 달라 사전에 자동 반영하지 않는다). 설명문은 설명 필드 여섯 개를 반영한다.
    """
    import pandas as pd  # noqa: E402
    sheet = pd.read_csv(sheet_path, dtype=str).fillna("")
    ok = sheet[(sheet["승인"].str.upper() == "O") & (sheet["검토자"].str.strip() != "")]
    if ok.empty:
        print("반영할 행이 없다(승인=O이고 검토자가 적힌 행)")
        return
    path = paths.DICTIONARY / "오개념.csv"
    mc = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    fields = {"검수": {"name_ko": "name_ko_제안", "category_id": "category_id", "our_code": "our_code_제안"},
              "설명문": {c: c for c in ("definition", "include_examples", "exclude_examples", "typical_trace",
                                        "student_explanation", "teacher_note")}}[task]
    for col in list(fields) + ["reviewed_by", "review_note"]:
        if col not in mc.columns:
            mc[col] = ""
    for r in ok.itertuples(index=False):
        row = r._asdict() if hasattr(r, "_asdict") else {}
        sel = mc.misconception_id == row["misconception_id"]
        for col, src in fields.items():
            mc.loc[sel, col] = row[src]
        mc.loc[sel, "reviewed_by"] = row["검토자"]
        mc.loc[sel, "review_note"] = row["검토메모"]
    mc.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"{len(ok)}개 오개념 반영: {path}")


def main():
    cfg = data_io.parse_config(CONFIG)
    if cfg["apply"]:
        apply_sheet(cfg["task"], cfg["apply"])
        return
    if isinstance(cfg["subtopics"], str):
        cfg["subtopics"] = [x.strip() for x in cfg["subtopics"].split(",") if x.strip()]
    cfg["workers"] = int(cfg["workers"])
    run = data_io.new_run(HERE, f"1-4-{cfg['task']}", cfg)
    import pandas as pd  # noqa: E402
    from concurrent.futures import ThreadPoolExecutor  # noqa: E402

    def one(tv):
        target, vars = tv
        p = llm_client.load_prompt(HERE / cfg["prompt_file"], cfg["prompt_stage"], **vars)
        out = llm_client.chat(cfg["provider"], p["system"], p[cfg["task"]], schema=OUTPUT_SCHEMA[cfg["task"]],
                              model=cfg["model"], cache_dir=CACHE_DIR)
        return to_sheet_rows(cfg["task"], target, out["parsed"])

    todo = targets(cfg)
    with ThreadPoolExecutor(max_workers=cfg["workers"]) as pool:
        rows = list(pool.map(one, todo))
    pd.DataFrame(rows, columns=SHEET_COLS[cfg["task"]]).to_csv(run.dir / f"{cfg['task']}_검토시트.csv", index=False,
                                                              encoding="utf-8-sig")
    print(f"오개념 {len(rows)}개 → {run.dir.name}/{cfg['task']}_검토시트.csv")
    data_io.finish_run(run, {"n_misconceptions": len(rows)}, note="사람 검토 후 --apply")


if __name__ == "__main__":
    main()
