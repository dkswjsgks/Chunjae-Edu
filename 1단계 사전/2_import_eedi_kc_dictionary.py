"""
[1단계 사전 / 2 KC·오개념 사전] 팀이 만든 Eedi 기반 KC·오개념 사전 엑셀을 사전/ 폴더의 CSV 형식으로 변환한다.

입력:
  - 사전/원본/Eedi_KC_오개념_사전_1-1.xlsx (시트: KC목록, 오개념사전, KC-오개념연결)
  - 사전/지식.csv (지식 이름 → knowledge_id)

출력:
  - 사전/KC.csv      KC 하나당 한 행. Eedi KC + 빈칸 KC 초안(status=draft). kc_group은 3_build_kc_groups.py가 채운다
  - 사전/오개념.csv  KC–오개념 연결 하나당 한 행(오개념 이름·원문 포함). 관련도 상·중은 use_in_mapping=1, 하는 0

실행 (레포 루트에서):
  python "1단계 사전/2_import_eedi_kc_dictionary.py"

주의:
  - 다시 실행하면 위 2개 파일을 덮어쓴다. 사람이 고친 내용은 원본 엑셀이나 아래 GAP_KCS 표에 반영하고,
    다시 실행한 뒤 3_build_kc_groups.py 실행, 4_오개념_정비 --apply 적용을 다시 한다.

빈칸 KC (GAP_KCS):
  대상 문항 = 첫 실험 지식의 문항 중, 원본 데이터 "토픽" 열 값(분석 데이터/토픽.csv의 topic_id, topic_name)이
  엑셀 KC목록 시트의 "대응 천재 토픽" 열 어느 행에도 나오지 않는 문항. 엑셀은 토픽 이름을 줄여 적었으므로 번호와 핵심어로 대조했다.
  - KC-N001  topic_5884126242602dc8 "5. 정수와 유리수의 덧셈과 뺄셈에 대한 기타 여러 분야의 활용"
             (유리수의 덧셈과 뺄셈의 혼합계산, 47문항, 풀이 916건). 엑셀 대응 토픽 값은 1~4번뿐
  - KC-N002  topic_8e4780804a7179f0 "2. 정수와 유리수 - 나열된 정수, 유리수에 대하여 옳거나 옳지 않은 것 고르기"
             (정수와 유리수의 대소 관계, 23문항, 풀이 663건). 엑셀의 "2." 값은 "2. 정수의 대소 관계"(topic_f0a1802ce26130b6)뿐
  - KC-N003  토픽 빈칸이 아니라 KC 범위 빈칸: 혼합계산 166문항 중 분수가 든 70문항이 쓰는 "부호 있는 분수의 덧셈·뺄셈"을
             핵심 KC로 다루는 행이 없음(엑셀 분수 KC는 초등 수준 양의 분수, 구분=보조)
  확정하려면 해당 문항 10개 이상과 대조해 이름·범위를 정하고 아래 표의 status를 active로 바꾼다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "공통"))

import pandas as pd  # noqa: E402

import paths  # noqa: E402

SOURCE = paths.DICTIONARY / "원본" / "Eedi_KC_오개념_사전_1-1.xlsx"
RELEVANCE_ORDER = {"상": 3, "중": 2, "하": 1}
KC_COLS = ["kc_id", "knowledge_id", "knowledge_name", "role", "kc_name_ko", "kc_group", "kc_group_name",
           "chunjae_topics", "construct_name_en", "eedi_construct_id", "eedi_subtopic", "source", "status", "review_note"]
MC_COLS = ["kc_id", "misconception_id", "name_ko", "name_en", "relevance", "use_in_mapping", "our_code_draft",
           "eedi_pct", "source", "status"]

# 엑셀 KC 목록에 대응 KC가 없는 토픽을 메우는 초안. 확정할 때 이 표를 직접 고친다(위 "빈칸 KC" 참고).
GAP_KCS = [
    ("KC-N001", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "상황(표·그림·실생활)을 유리수의 덧셈·뺄셈 식으로 나타내 계산하기",
     "5. 정수와 유리수의 덧셈과 뺄셈에 대한 기타 여러 분야의 활용",
     "대응 KC 없던 토픽(47문항, 풀이 916건). 기온차 표, 사다리타기, 주사위·전개도 문항 포함. 하나로 둘지 나눌지 검토"),
    ("KC-N002", "정수와 유리수의 대소 관계", "핵심",
     "수를 양의 정수·음의 정수·0·정수가 아닌 유리수로 분류하기",
     "2. 정수와 유리수 - 나열된 정수, 유리수에 대하여 옳거나 옳지 않은 것 고르기",
     "대응 KC 없던 토픽(23문항, 풀이 663건). 약분하면 정수가 되는 분수(예: -6/3) 포함. Eedi Identifying Types of Number 참고"),
    ("KC-N003", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "부호가 있는 분수의 덧셈과 뺄셈(통분 후 부호 규칙 적용)",
     "1. 혼합 계산(분수)",
     "분수 KC가 초등 수준 양의 분수(보조)만 있음. 혼합계산 166문항 중 70문항이 분수"),
]


def main():
    xl = pd.ExcelFile(SOURCE)
    kc = xl.parse("KC목록")
    mc = xl.parse("오개념사전")
    link = xl.parse("KC-오개념연결")
    knowledge = pd.read_csv(paths.DICTIONARY / "지식.csv", encoding="utf-8-sig", dtype=str)
    kid = dict(zip(knowledge.knowledge_name, knowledge.knowledge_id))

    unknown = set(kc["천재 지식단위"]) - set(kid)
    if unknown:
        raise ValueError(f"지식.csv에 없는 지식단위: {unknown}")

    # KC 사전
    kc_rows = pd.DataFrame({
        "kc_id": "KC-E" + kc["Eedi ConstructId"].astype(str),
        "knowledge_name": kc["천재 지식단위"],
        "role": kc["구분"],
        "kc_name_ko": kc["KC(한국어)"],
        "construct_name_en": kc["ConstructName(원문)"].str.strip(),
        "eedi_construct_id": kc["Eedi ConstructId"].astype(str),
        "eedi_subtopic": kc["SubTopic"],
        "chunjae_topics": kc["대응 천재 토픽"],
        "source": "eedi",
        "status": "active",
        "review_note": "",
    })
    gap = pd.DataFrame([{
        "kc_id": g[0], "knowledge_name": g[1], "role": g[2], "kc_name_ko": g[3], "construct_name_en": "",
        "eedi_construct_id": "", "eedi_subtopic": "", "chunjae_topics": g[4],
        "source": "new", "status": g[6] if len(g) > 6 else "draft", "review_note": g[5],
    } for g in GAP_KCS])
    kc_dict = pd.concat([kc_rows, gap], ignore_index=True)
    if kc_dict.kc_id.duplicated().any():
        raise ValueError("중복 kc_id")
    kc_dict.insert(1, "knowledge_id", kc_dict.knowledge_name.map(kid))
    kc_dict["kc_group"] = ""
    kc_dict["kc_group_name"] = ""
    kc_dict = kc_dict[KC_COLS]

    # 오개념: KC–오개념 연결 하나당 한 행. 오개념 이름·원문·코드 초안은 오개념마다 같고,
    # 여러 지식단위에 걸친 오개념은 관련도가 가장 높은 행의 이름을 쓴다
    mc = mc.assign(_rank=mc["관련도"].map(RELEVANCE_ORDER))
    codes = mc.groupby("Eedi MisconceptionId")["우리 코드(초안)"].agg(lambda s: ";".join(sorted(set(s.dropna()))))
    best = mc.sort_values("_rank", ascending=False).drop_duplicates("Eedi MisconceptionId").set_index("Eedi MisconceptionId")
    info = pd.DataFrame({
        "misconception_id": "MC-E" + best.index.astype(str),
        "name_ko": best["오개념(한국어)"].values,
        "name_en": best["MisconceptionName(원문)"].values,
        "our_code_draft": codes.reindex(best.index).values,
    })
    links = pd.DataFrame({
        "kc_id": "KC-E" + link["Eedi ConstructId"].astype(str),
        "misconception_id": "MC-E" + link["Eedi MisconceptionId"].astype(str),
        "relevance": link["관련도"],
        "eedi_pct": link["비중(%)"],
    })
    links["use_in_mapping"] = links.relevance.isin(["상", "중"]).astype(int)
    links["source"] = "eedi"
    links["status"] = "active"
    missing_kc = set(links.kc_id) - set(kc_dict.kc_id)
    if missing_kc:
        raise ValueError(f"KC목록에 없는 KC가 연결표에 있음: {sorted(missing_kc)[:5]}")
    mc_table = links.merge(info, on="misconception_id", how="left", validate="many_to_one")
    if mc_table.name_ko.isna().any():
        raise ValueError("오개념사전 시트에 없는 오개념이 연결표에 있음")
    mc_table = mc_table[MC_COLS]

    kc_dict.to_csv(paths.DICTIONARY / "KC.csv", index=False, encoding="utf-8-sig")
    mc_table.to_csv(paths.DICTIONARY / "오개념.csv", index=False, encoding="utf-8-sig")
    print(f"KC {len(kc_dict)} (Eedi {len(kc_rows)}, 초안 {len(gap)})")
    print(f"오개념 {mc_table.misconception_id.nunique()}개, KC–오개념 연결 {len(mc_table)}행 "
          f"(매핑 후보 {mc_table.use_in_mapping.sum()}, 제외 {(mc_table.use_in_mapping == 0).sum()})")


if __name__ == "__main__":
    main()
