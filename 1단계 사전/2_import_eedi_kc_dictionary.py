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

빈칸 KC (GAP_KCS) — 2026-11-19 확정:
  대상 문항 = 첫 실험 지식의 문항 중, 원본 데이터 "토픽" 열 값(분석 데이터/토픽.csv의 topic_id, topic_name)이
  엑셀 KC목록 시트의 "대응 천재 토픽" 열 어느 행에도 나오지 않는 문항. 엑셀은 토픽 이름을 줄여 적었으므로 번호와 핵심어로 대조했다.
  - 토픽 빈칸 ①  topic_5884126242602dc8 "5. 정수와 유리수의 덧셈과 뺄셈에 대한 기타 여러 분야의 활용"
             (유리수의 덧셈과 뺄셈의 혼합계산, 47문항, 풀이 916건). 엑셀 대응 토픽 값은 1~4번뿐.
             47문항을 모두 읽고 계산 부분(음수 덧셈·뺄셈)은 기존 KC로 설명되는 것을 확인했다. 기존 KC에 없는 "상황 읽기" 부분만
             세 가지로 나눠 KC-N001, N004, N005로 만들었다(근거: 1단계 사전/KC_확정_근거.md).
  - 토픽 빈칸 ②  topic_8e4780804a7179f0 "2. 정수와 유리수 - 나열된 정수, 유리수에 대하여 옳거나 옳지 않은 것 고르기"
             (정수와 유리수의 대소 관계, 23문항, 풀이 663건). 엑셀의 "2." 값은 "2. 정수의 대소 관계"(topic_f0a1802ce26130b6)뿐.
             → KC-N002 하나로 확정.
  - KC 범위 빈칸  혼합계산 166문항 중 분수가 든 70문항(풀이 1,594건, 정답률 40.9%, 분수 없는 문항은 53.5%)이 쓰는
             "부호 있는 분수의 덧셈·뺄셈"을 핵심 KC로 다루는 행이 없음(엑셀 분수 KC는 초등 수준 양의 분수, 구분=보조) → KC-N003.
  ID 규칙: 한 번 낸 KC ID와 묶음 번호는 바꾸지 않는다. 새 KC는 표의 맨 아래에 추가한다(KG 번호가 순서대로 붙기 때문).
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

# 엑셀 KC 목록에 대응 KC가 없는 토픽·범위를 메우는 KC. 고칠 때 이 표를 직접 고친다(위 "빈칸 KC" 참고).
GAP_KCS = [
    ("KC-N001", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "표·그림에서 최댓값과 최솟값(또는 기준값 대비 값)을 찾아 차 구하기",
     "5. 정수와 유리수의 덧셈과 뺄셈에 대한 기타 여러 분야의 활용",
     "9문항(기온표·일교차·높이·몸무게·신체나이). 대표 오답: 최저 기온의 부호를 무시하고 뺌(33.5-2.7=30.8, 그 문항 오답의 46%). "
     "차 계산은 기존 음수 덧셈·뺄셈 KC와 함께 배정. Eedi 참고(사전 미포함): 3849 두 유리수 사이 거리", "active"),
    ("KC-N002", "정수와 유리수의 대소 관계", "핵심",
     "수를 양의 정수·음의 정수·0·정수가 아닌 유리수로 분류하기",
     "2. 정수와 유리수 - 나열된 정수, 유리수에 대하여 옳거나 옳지 않은 것 고르기",
     "23문항 전부 확인(개수 세기 7, 설명 옳고 그름 14, 기타 2). 22문항에 분수가 있고 약분하면 정수가 되는 수(-6/3, 12/6)가 함정. "
     "7문항은 절댓값·대소 비교도 묻는다 → 이 KC와 기존 대소·절댓값 KC를 같이 배정. Eedi Identifying Types of Number는 무리수 구분뿐이라 맞지 않음", "active"),
    ("KC-N003", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "부호가 있는 분수의 덧셈과 뺄셈(통분 후 부호 규칙 적용)",
     "1. 혼합 계산(분수)",
     "분수 KC가 초등 수준 양의 분수(보조)만 있음. 혼합계산 166문항 중 70문항이 분수(식 계산 19, ~만큼 큰/작은 수 24, 빈칸 5, 기타 22). "
     "풀이 1,594건 정답률 40.9%(분수 없는 문항 53.5%). 대표 오답: 부호를 무시하고 더함(1/4+5/6+4/3=29/12)", "active"),
    ("KC-N004", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "변화·득실(등락폭, 점수, 이동, 시차)을 부호 있는 수로 나타내 누적하기",
     "5. 정수와 유리수의 덧셈과 뺄셈에 대한 기타 여러 분야의 활용",
     "12문항(주가, 골프 타수, 계단 가위바위보, 사다리타기, 시차). 올라감·내려감, 이김·짐을 +·-로 바꾸는 단계가 핵심. 정답률 49%", "active"),
    ("KC-N005", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "주어진 조건(합이 같음, 마주 보는 면의 합, 절댓값 조건)을 식으로 나타내 문자의 값 구하기",
     "5. 정수와 유리수의 덧셈과 뺄셈에 대한 기타 여러 분야의 활용",
     "22문항(합이 같은 표·삼각형 15, 전개도·주사위 3, 조건으로 수 정하기 3, 잘못 계산한 식 되돌리기 1). 정답률 35%로 가장 낮음", "active"),
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
