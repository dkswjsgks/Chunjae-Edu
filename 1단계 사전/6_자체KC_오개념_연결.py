"""
[1단계 사전 / 6 자체 KC 오개념 연결] 우리가 만든 KC(source=new)에는 Eedi 연결표가 없어 오개념이 하나도 붙어 있지 않다.
사전에 이미 있는 Eedi 오개념(첫 실험 지식 2개의 KC에 연결된 것) 중에서 각 자체 KC와 내용이 맞는 것을 LLM이 골라
연결 초안을 만든다. 사람이 확인한 뒤 --apply로 사전/오개념.csv에 행으로 추가한다.

실행 (레포 루트에서):
  python "1단계 사전/6_자체KC_오개념_연결.py" --provider openai
  python "1단계 사전/6_자체KC_오개념_연결.py" --apply "<연결_초안.csv>"

입력: 사전/KC.csv, 사전/오개념.csv, (근거 문항) 2단계 문항KC배정 결과 --assign-run
출력: 1단계 사전/결과/6-자체KC연결-<날짜>-<번호>/연결_초안.csv (승인, 검토자, 검토메모 열은 사람이 채운다)
반영: 연결 하나당 사전/오개념.csv에 한 행. 오개념 단위 값(이름, 분류, 코드 등)은 기존 행에서 복사하고,
      kc_id·relevance·use_in_mapping만 바꾼다. eedi_pct는 Eedi 값이 없으므로 비운다. status=draft로 표시한다.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "공통"))

import pandas as pd  # noqa: E402

import data_io  # noqa: E402
import llm_client  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402

CONFIG = {
    "provider": "openai",
    "model": None,
    "assign_run": "2-2-KC배정-openai-original-20261119-07",   # 근거 문항(KC 배정이 있는 실행)
    "max_links": 8,                      # KC마다 연결할 오개념 최대 수
    "n_examples": 3,                     # 프롬프트에 보여 줄 근거 문항 풀이 단계 수
    "apply": None,                       # 검토한 시트 경로. 주면 사전에 반영만 한다
    "workers": 4,
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}
CACHE_DIR = HERE / "_cache_own_kc_link"

SYSTEM = "너는 한국 중학교 1학년 수학(정수와 유리수) 교사다. 학생의 오답 원인(오개념)과 지식 요소(KC)를 짝짓는다."

USER = """[KC] {kc_id} {kc_name}
메모: {note}
이 KC가 붙은 문항의 풀이 단계 예시:
{examples}

[후보 오개념] (MC-ID | 이름 | 상위 분류)
{pool}

위 KC의 지식을 학생이 제대로 쓰지 못할 때 나타나는 오개념을 후보에서 고른다.
- 최대 {max_links}개. 관련이 뚜렷한 것만 고르고, 없으면 빈 목록을 돌려준다. 개수를 채우려고 억지로 고르지 않는다.
- relevance: 상 = 이 KC의 핵심 기능을 틀리는 오개념 / 중 = 이 KC의 풀이에서 나올 수 있는 오개념. 하는 쓰지 않는다.
- reason: 왜 이 KC와 이어지는지 한 문장.
- 후보 목록에 없는 ID는 쓰지 않는다."""

SCHEMA = {
    "type": "object",
    "properties": {"links": {"type": "array", "items": {
        "type": "object",
        "properties": {"misconception_id": {"type": "string"}, "relevance": {"type": "string", "enum": ["상", "중"]},
                       "reason": {"type": "string"}},
        "required": ["misconception_id", "relevance", "reason"], "additionalProperties": False}}},
    "required": ["links"], "additionalProperties": False,
}


def candidate_pool(kc, mc, ids):
    """첫 실험 지식의 KC에 연결된 오개념(고유). 이름은 검수한 한국어 이름, 없으면 원문"""
    scope = set(kc[kc.knowledge_id.isin(ids)].kc_id)
    m = mc[mc.kc_id.isin(scope)].drop_duplicates("misconception_id")
    m = m.assign(label=m.name_ko.where(m.name_ko != "", m.name_en))
    return m


def examples_for(kc_id, assign, n):
    s = assign[assign.kc_id == kc_id].drop_duplicates("item_id").head(n)
    return "\n".join(f"- {r.step}" for r in s.itertuples()) or "- (예시 없음)"


def make_sheet(cfg):
    kc = data_io.load_dictionary("KC")
    mc = data_io.load_dictionary("오개념")
    pool = candidate_pool(kc, mc, data_io.knowledge_ids(cfg["knowledge"]))
    pool_text = "\n".join(f"{r.misconception_id} | {r.label} | {r.category_id or '-'}" for r in pool.itertuples())
    pool_ids = set(pool.misconception_id)
    assign = pd.read_csv(paths.REPO / "2단계 Q행렬" / "2_문항KC배정" / "결과" / cfg["assign_run"] / "문항_KC.csv",
                         dtype=str, keep_default_na=False, encoding="utf-8-sig")
    targets = kc[(kc.source == "new") & (kc.status == "active")]
    run = data_io.new_run(HERE, "6-자체KC연결", cfg)

    def one(r):
        user = USER.format(kc_id=r.kc_id, kc_name=r.kc_name_ko, note=r.review_note[:600],
                           examples=examples_for(r.kc_id, assign, int(cfg["n_examples"])), pool=pool_text,
                           max_links=cfg["max_links"])
        out = llm_client.chat(cfg["provider"], SYSTEM, user, schema=SCHEMA, model=cfg["model"], cache_dir=CACHE_DIR)
        rows = []
        for l in out["parsed"]["links"][:int(cfg["max_links"])]:
            if l["misconception_id"] not in pool_ids:
                continue
            p = pool[pool.misconception_id == l["misconception_id"]].iloc[0]
            rows.append({"kc_id": r.kc_id, "kc_name_ko": r.kc_name_ko, "misconception_id": l["misconception_id"],
                         "name_ko": p.name_ko or "", "name_en": p.name_en, "category_id": p.category_id,
                         "relevance": l["relevance"], "reason": l["reason"], "승인": "", "검토자": "", "검토메모": ""})
        return rows

    with ThreadPoolExecutor(max_workers=int(cfg["workers"])) as ex:
        parts = list(ex.map(one, list(targets.itertuples())))
    sheet = pd.DataFrame([x for p in parts for x in p])
    sheet.to_csv(run.dir / "연결_초안.csv", index=False, encoding="utf-8-sig")
    n_kc = sheet.kc_id.nunique() if len(sheet) else 0
    print(f"자체 KC {len(targets)}개 중 {n_kc}개에 오개념 {len(sheet)}개 연결 초안 → {run.dir / '연결_초안.csv'}")
    data_io.finish_run(run, {"n_kc": len(targets), "kc_with_links": n_kc, "n_links": len(sheet)})


def apply_sheet(path):
    """승인=O이고 검토자가 있는 행만 사전/오개념.csv에 추가한다. 이미 있는 (kc_id, misconception_id)는 건너뛴다"""
    sheet = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    ok = sheet[(sheet.승인 == "O") & (sheet.검토자 != "")]
    f = paths.DICTIONARY / "오개념.csv"
    mc = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    have = set(zip(mc.kc_id, mc.misconception_id))
    new = []
    for r in ok.itertuples():
        if (r.kc_id, r.misconception_id) in have:
            continue
        base = mc[mc.misconception_id == r.misconception_id].iloc[0].to_dict()
        base.update(kc_id=r.kc_id, relevance=r.relevance, use_in_mapping="1", eedi_pct="", status="draft")
        new.append(base)
    out = pd.concat([mc, pd.DataFrame(new, columns=mc.columns)], ignore_index=True)
    out.to_csv(f, index=False, encoding="utf-8-sig")
    print(f"{len(new)}개 연결 반영: {f}")


def main():
    cfg = data_io.parse_config(CONFIG)
    cfg["workers"] = int(cfg["workers"])
    if cfg["apply"]:
        apply_sheet(cfg["apply"])
    else:
        make_sheet(cfg)


if __name__ == "__main__":
    main()
