"""
[2단계 Q행렬 / 4 통합 보기] 첫 실험 단원의 문항마다 단원 분류 - 붙은 KC - KC에 연결된 오개념을 한 파일에서 보는 CSV를 만든다.

실행 (레포 루트에서):
  python "2단계 Q행렬/4_build_overview.py" --kc-run 2-2-KC배정-openai-original-20261119-07

입력: 2단계 2_문항KC배정/결과/<kc-run>/문항_KC.csv, 문항_누락.csv / 분석 데이터/문항.csv / 사전/KC.csv, 오개념.csv
출력: 2단계 Q행렬/2_문항KC배정/결과/<kc-run>/문항_KC_오개념.csv  (UTF-8 BOM, 엑셀에서 바로 열린다. 배정 결과와 같은 실행 폴더에 둔다)

한 행 = 문항 하나 × 그 문항에 붙은 KC 하나. 문항에 KC가 안 붙었으면 그 문항은 KC 칸이 빈 한 행만 둔다.
- 단원 분류: 지식, 대단원, 중단원, 소단원, 토픽, 문항ID, 문항유형, 정답키
- 문항 요약·missing: 문항의 첫 행에만 적는다(길어서 행마다 반복하지 않는다)
- KC: 순서, ID, 이름, 역할(핵심/보조), 출처(eedi=엑셀·Eedi 공개 데이터 / new=우리가 만든 것), 묶음, 풀이 단계
- 오개념: 이 KC에 연결된 매핑 후보 오개념(관련도 상·중)의 수와 목록. 목록은 관련도 상→중, Eedi 비중이 큰 순으로 앞에서 10개까지
  (전체는 사전/오개념.csv). 상위 오류 유형(CAT)은 사람이 검수해 승인한 뒤 사전에 들어가므로 아직 이 파일에 없다
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "공통"))

import pandas as pd  # noqa: E402

import data_io  # noqa: E402
import paths  # noqa: E402

CONFIG = {"kc_run": "", "max_mc": 10}
REL = {"상": 0, "중": 1, "하": 2}


def main():
    cfg = data_io.parse_config(CONFIG)
    run = HERE / "2_문항KC배정" / "결과" / cfg["kc_run"]
    assigned = pd.read_csv(run / "문항_KC.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = pd.read_csv(run / "문항_누락.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    items = data_io.load_items()
    kc = data_io.load_dictionary("KC").set_index("kc_id")
    mc = data_io.load_dictionary("오개념")
    mc = mc[mc.use_in_mapping == "1"].copy()
    mc["_r"] = mc.relevance.map(REL).fillna(3)
    mc["_p"] = pd.to_numeric(mc.eedi_pct, errors="coerce").fillna(0)
    mc = mc.sort_values(["kc_id", "_r", "_p"], ascending=[True, True, False])
    by_kc = {k: g for k, g in mc.groupby("kc_id")}
    max_mc = int(cfg["max_mc"])

    def mc_cell(kc_id):
        g = by_kc.get(kc_id)
        if g is None or g.empty:
            return 0, ""
        parts = [f"[{r.relevance}] {r.misconception_id} {r.name_ko or r.name_en}" for r in g.head(max_mc).itertuples()]
        if len(g) > max_mc:
            parts.append(f"... 외 {len(g) - max_mc}개")
        return len(g), " ; ".join(parts)

    assigned = assigned[assigned.kc_id != ""]
    by_item = {}
    for r in assigned.itertuples():
        by_item.setdefault(r.item_id, {}).setdefault(r.kc_id, []).append((int(r.step_index), r.step))
    miss = dict(zip(missing.item_id, missing.missing))

    rows = []
    for it in items.sort_values(["knowledge_name", "topic_name", "item_id"]).itertuples():
        base = {"지식": it.knowledge_name, "대단원": it.major_name, "중단원": it.middle_name, "소단원": it.minor_name,
                "토픽": it.topic_name, "문항ID": it.item_id, "문항유형": it.item_form, "정답키": it.answer_raw}
        kcs = by_item.get(it.item_id, {})
        # KC 순서: 처음 쓰인 풀이 단계 순
        order = sorted(kcs, key=lambda k: min(s for s, _ in kcs[k]))
        first = {"문항_요약": " ".join(it.question_text.split())[:90], "missing": miss.get(it.item_id, "")}
        if not order:
            rows.append({**base, **first, "붙은KC수": 0, "KC순서": "", "KC_ID": "", "KC이름": "", "KC역할": "", "KC출처": "",
                         "KC묶음": "", "풀이단계": "", "연결오개념수": "", "연결오개념": ""})
            continue
        for i, k in enumerate(order, 1):
            info = kc.loc[k] if k in kc.index else None
            n_mc, cell = mc_cell(k)
            steps = kcs[k]
            rows.append({**base, **(first if i == 1 else {"문항_요약": "", "missing": ""}), "붙은KC수": len(order),
                         "KC순서": i, "KC_ID": k, "KC이름": info.kc_name_ko if info is not None else "",
                         "KC역할": info.role if info is not None else "", "KC출처": info.source if info is not None else "",
                         "KC묶음": info.kc_group_name if info is not None else "",
                         "풀이단계": " / ".join(f"{s}단계" for s, _ in sorted(steps)),
                         "연결오개념수": n_mc, "연결오개념": cell})
    out = pd.DataFrame(rows)
    OUT = run / "문항_KC_오개념.csv"
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"{OUT.relative_to(HERE.parent)}: {len(out)}행, 문항 {out['문항ID'].nunique()}개, KC 없는 문항 {int((out.KC_ID == '').sum())}개")


if __name__ == "__main__":
    main()
