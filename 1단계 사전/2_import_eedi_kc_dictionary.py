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
  - 토픽 빈칸 ③  topic_674de561a73ccf58 "3. 어떤 수보다 ~만큼 큰 수, 작은 수" (51문항): 엑셀 KC가 두 개뿐이고 "~보다 ~만큼 큰(작은) 수"를
             식으로 나타내는 KC가 없음 → KC-N006 (2단계 1차 배정의 missing에서 발견)
  - 대소 관계 빈틈  분수·소수가 섞인 비교와 양수 대소 → KC-N007과 Eedi KC 2개(EXTRA_EEDI_KCS). KC-N002는 범위를 넓힘
  2026-11-19 Eedi 우선 정리: N003·N004·N007은 Eedi KC 조합(E246~264 음수 덧셈·뺄셈, E3882, E455·E457·E3124 분수 계산,
             E296~E421 소수·분수 비교와 변환)으로 대체해 표에서 뺐다. 남은 임의 KC는 Eedi에 해당 지식이 없는 N001, N002, N005, N006이다.
  ID 규칙: 한 번 낸 KC ID와 묶음 번호는 바꾸지 않는다. 새 KC는 표의 맨 아래에 추가한다(KG 번호가 순서대로 붙기 때문).
  Eedi에서 더 가져온 KC(EXTRA_EEDI_KCS)는 KC.csv 맨 끝에 붙여서 기존 묶음 번호가 밀리지 않게 한다.
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
     "자연수·정수·유리수의 뜻과 포함 관계를 알고 수를 양의 정수·음의 정수·0·정수가 아닌 유리수로 분류하기",
     "2. 정수와 유리수 - 나열된 정수, 유리수에 대하여 옳거나 옳지 않은 것 고르기 / 3. 정수와 유리수 - 정수, 유리수의 일반적인 성질로 옳거나 옳지 않은 것 고르기",
     "23문항 전부 확인(개수 세기 7, 설명 옳고 그름 14, 기타 2). 22문항에 분수가 있고 약분하면 정수가 되는 수(-6/3, 12/6)가 함정. "
     "7문항은 절댓값·대소 비교도 묻는다 → 이 KC와 기존 대소·절댓값 KC를 같이 배정. Eedi Identifying Types of Number는 무리수 구분뿐이라 맞지 않음. "
     "2026-11-19 범위 확대: 1차 배정에서 \"자연수⊂정수⊂유리수 포함 관계\" 부족 표시가 3번 토픽에서도 나와 이름과 토픽을 넓힘", "active"),
    ("KC-N005", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "주어진 조건(합이 같음, 마주 보는 면의 합, 절댓값 조건)을 식으로 나타내 문자의 값 구하기",
     "5. 정수와 유리수의 덧셈과 뺄셈에 대한 기타 여러 분야의 활용",
     "22문항(합이 같은 표·삼각형 15, 전개도·주사위 3, 조건으로 수 정하기 3, 잘못 계산한 식 되돌리기 1). 정답률 35%로 가장 낮음", "active"),
    ("KC-N006", "유리수의 덧셈과 뺄셈의 혼합계산", "핵심",
     "\"a보다 b만큼 큰(작은) 수\"를 a+b(a-b)로 나타내기(b가 음수인 경우 포함)",
     "3. 어떤 수보다 ~만큼 큰 수, 작은 수",
     "3번 토픽 51문항 중 약 46문항이 이 문장 형식(예: 3보다 -5만큼 큰 수, -1보다 -4만큼 작은 수). 엑셀은 이 토픽에 KC 두 개만 붙였고 "
     "1차 배정에서 47문항에 missing이 적히고 그중 34문항이 이 지식이었다. b가 음수일 때 \"큰\"과 \"작은\"의 부호 처리가 핵심. "
     "분수 계산은 N003, 정수 개수 세기는 다른 지식 단위라 따로 둔다", "active"),
]


# 엑셀 KC 목록에 없어서 Eedi 공개 데이터(외부 자료/Eedi)에서 더 가져오는 KC. 역할은 보조(초등 수준).
# (ConstructId, 지식 이름, 역할, 한국어 KC 이름, 대응 천재 토픽, 메모)
EXTRA_EEDI_KCS = [
    (297, "정수와 유리수의 대소 관계", "보조", "자릿수가 다른 양의 소수의 대소 비교", "1. 유리수의 대소 관계",
     "1차 배정에서 양수 대소·소수 변환 부족 표시. 초등 수준이라 보조"),
    (415, "정수와 유리수의 대소 관계", "보조", "분모가 서로 배수가 아닌 양의 분수의 대소 비교(통분)", "1. 유리수의 대소 관계",
     "1차 배정에서 양수 대소·통분 부족 표시. 초등 수준이라 보조"),
    (293, "정수와 유리수의 대소 관계", "보조", "한 자리 소수가 수직선 위에서 어디에 놓이는지 찾기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(수직선 위의 양의 소수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (294, "정수와 유리수의 대소 관계", "보조", "두 자리 소수가 수직선 위에서 어디에 놓이는지 찾기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(수직선 위의 양의 소수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (296, "정수와 유리수의 대소 관계", "보조", "자릿수가 같은 양의 소수의 대소 비교", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(소수 대소). 한국어 이름은 LLM 초벌, 검수 필요"),
    (298, "정수와 유리수의 대소 관계", "보조", "자릿수가 같은 양의 소수를 부등호로 비교하기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(소수 대소(부등호)). 한국어 이름은 LLM 초벌, 검수 필요"),
    (299, "정수와 유리수의 대소 관계", "보조", "자릿수가 다른 양의 소수를 부등호로 비교하기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(소수 대소(부등호)). 한국어 이름은 LLM 초벌, 검수 필요"),
    (413, "정수와 유리수의 대소 관계", "보조", "분모가 같은 양의 분수의 대소 비교", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 대소). 한국어 이름은 LLM 초벌, 검수 필요"),
    (414, "정수와 유리수의 대소 관계", "보조", "분모가 서로 배수인 양의 분수의 대소 비교", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 대소). 한국어 이름은 LLM 초벌, 검수 필요"),
    (417, "정수와 유리수의 대소 관계", "보조", "분모가 같은 양의 분수를 부등호로 비교하기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 대소(부등호)). 한국어 이름은 LLM 초벌, 검수 필요"),
    (418, "정수와 유리수의 대소 관계", "보조", "분모가 서로 배수인 양의 분수를 부등호로 비교하기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 대소(부등호)). 한국어 이름은 LLM 초벌, 검수 필요"),
    (419, "정수와 유리수의 대소 관계", "보조", "분모가 서로 배수가 아닌 양의 분수를 부등호로 비교하기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 대소(부등호)). 한국어 이름은 LLM 초벌, 검수 필요"),
    (3320, "정수와 유리수의 대소 관계", "보조", "분자가 같은 양의 분수를 부등호로 비교하기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 대소(부등호)). 한국어 이름은 LLM 초벌, 검수 필요"),
    (420, "정수와 유리수의 대소 관계", "보조", "양의 단위분수를 수직선 위에 나타내기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(수직선 위의 양의 분수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (421, "정수와 유리수의 대소 관계", "보조", "양의 진분수(분자가 1이 아닌 분수)를 수직선 위에 나타내기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(수직선 위의 양의 분수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (362, "정수와 유리수의 대소 관계", "보조", "1 미만의 분수를 소수 한 자리 유한소수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수→소수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (363, "정수와 유리수의 대소 관계", "보조", "1 미만의 분수를 소수 두 자리 유한소수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수→소수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (364, "정수와 유리수의 대소 관계", "보조", "1 미만의 분수를 소수 세 자리 이상 유한소수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수→소수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (365, "정수와 유리수의 대소 관계", "보조", "1보다 큰 분수를 유한소수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수→소수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (366, "정수와 유리수의 대소 관계", "보조", "1 미만의 소수 한 자리 유한소수를 분수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(소수→분수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (367, "정수와 유리수의 대소 관계", "보조", "1 미만의 소수 두 자리 유한소수를 분수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(소수→분수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (368, "정수와 유리수의 대소 관계", "보조", "1 미만의 소수 세 자리 이상 유한소수를 분수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(소수→분수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (369, "정수와 유리수의 대소 관계", "보조", "1보다 큰 유한소수를 분수로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(소수→분수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (3599, "정수와 유리수의 대소 관계", "보조", "분모가 10, 100인 분수와 소수 사이를 서로 바꾸기", "1. 유리수의 대소 관계",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수↔소수). 한국어 이름은 LLM 초벌, 검수 필요"),
    (328, "정수와 유리수의 대소 관계", "보조", "유리수와 무리수 구분하기", "2. 정수와 유리수 - 나열된 정수, 유리수에 대하여 옳거나 옳지 않은 것 고르기",
     "2026-11-19 Eedi 우선 원칙으로 추가(수의 분류(무리수는 중1 범위 밖이라 보조)). 한국어 이름은 LLM 초벌, 검수 필요"),
    (455, "유리수의 덧셈과 뺄셈의 혼합계산", "보조", "분수의 덧셈·뺄셈이 필요한 문제 풀기", "1. 혼합 계산(분수)",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 덧셈·뺄셈 문제). 한국어 이름은 LLM 초벌, 검수 필요"),
    (457, "유리수의 덧셈과 뺄셈의 혼합계산", "보조", "분수가 섞인 식을 계산 순서에 맞게 계산하기", "1. 혼합 계산(분수)",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수 혼합계산). 한국어 이름은 LLM 초벌, 검수 필요"),
    (3124, "유리수의 덧셈과 뺄셈의 혼합계산", "보조", "분수와 정수의 뺄셈", "1. 혼합 계산(분수)",
     "2026-11-19 Eedi 우선 원칙으로 추가(분수와 정수의 뺄셈). 한국어 이름은 LLM 초벌, 검수 필요"),
]
# 위 construct에 붙은 오개념 중 수의 크기 비교에 쓰이는 것의 한국어 이름(LLM 초벌, 검수 필요). 나머지는 관련도 하(매핑 후보 제외)로 둔다.
EXTRA_MC_KO = {
    14600: "소수점 뒤에 값이 있는 수가 값이 없는 수보다 크다는 것을 이해하지 못함",
    23897: "소수점 아래 숫자가 클수록 자릿값과 무관하게 더 큰 수라고 믿음",
    22586: "첫 번째 유효숫자가 큰 수가 자릿값과 무관하게 더 크다고 믿음",
    18077: "소수의 대소를 비교할 때 소수점이 중요하지 않다고 믿음",
    19373: "정수가 소수점 앞 숫자가 같은 소수보다 크다고 믿음(예: 5가 5.9보다 큼)",
    19768: "가장 작은 수와 가장 큰 수를 혼동함",
    18802: "소수 자릿수가 많을수록 더 작은 수라고 믿음",
    26120: "소수점이 수의 크기에 영향을 주지 않는다고 보고 숫자만으로 비교함",
    26442: "분수를 소수로 바꿀 때 분자와 분모를 소수점으로 이어 붙임",
    15450: "분수와 소수가 \"분자.분모\"로 대응한다고 믿음(예: 3/4=3.4)",
    22647: "분자와 관계없이 분모가 작을수록 더 큰 분수라고 믿음",
    19420: "분모와 관계없이 분자가 작을수록 더 작은 분수라고 믿음",
    19419: "분자와 관계없이 분모가 작을수록 더 작은 분수라고 믿음",
    15582: "분수를 정렬할 때 분모만 비교하면 된다고 믿음",
    15438: "분모가 가장 큰 분수가 분자와 무관하게 가장 작다고 믿음",
    14068: "분수를 정렬할 때 가장 작은 것과 가장 큰 것을 혼동함",
    17372: "분수를 정렬할 때 분자만 비교하면 된다고 믿음",
    14090: "분모가 큰 분수가 크기도 더 크다고 믿음",
    18665: "분자와 관계없이 분모가 클수록 더 작은 분수라고 믿음",
    15132: "분수를 비교할 때 통분하지 않음",
    18664: "분자와 관계없이 분모가 클수록 더 큰 분수라고 믿음",
}


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
    cmap = pd.read_csv(paths.EEDI / "construct-map.csv").drop_duplicates("ConstructId").set_index("ConstructId")
    extra_kc = pd.DataFrame([{
        "kc_id": f"KC-E{c}", "knowledge_name": k, "role": r, "kc_name_ko": ko, "construct_name_en": cmap.loc[c, "ConstructName"].strip(),
        "eedi_construct_id": str(c), "eedi_subtopic": cmap.loc[c, "SubTopicName"], "chunjae_topics": topics,
        "source": "eedi", "status": "active", "review_note": note,
    } for c, k, r, ko, topics, note in EXTRA_EEDI_KCS])
    kc_dict = pd.concat([kc_rows, gap, extra_kc], ignore_index=True)
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
    # 추가 Eedi KC의 오개념 연결. 이미 사전에 있는 오개념은 이름·코드를 그대로 쓰고 관련도 중,
    # 새 오개념은 EXTRA_MC_KO에 있으면 관련도 중, 없으면 하
    mmap = pd.read_csv(paths.EEDI / "misconception-map.csv")
    known = info.set_index("misconception_id")
    rows = []
    for c, *_ in EXTRA_EEDI_KCS:
        for r in mmap[mmap.ConstructId == c].itertuples():
            mid = f"MC-E{r.MisconceptionId}"
            if mid in known.index:
                ko, name_en, code, rel = known.loc[mid, "name_ko"], known.loc[mid, "name_en"], known.loc[mid, "our_code_draft"], "중"
            else:
                ko, name_en, code = EXTRA_MC_KO.get(r.MisconceptionId, ""), r.MisconceptionName, ""
                rel = "중" if r.MisconceptionId in EXTRA_MC_KO else "하"
            rows.append({"kc_id": f"KC-E{c}", "misconception_id": mid, "name_ko": ko, "name_en": name_en, "relevance": rel,
                         "use_in_mapping": int(rel in ("상", "중")), "our_code_draft": code,
                         "eedi_pct": r.PercentageMisconceptionExistsInThisConstruct, "source": "eedi", "status": "active"})
    mc_table = pd.concat([mc_table, pd.DataFrame(rows)[MC_COLS]], ignore_index=True)
    if mc_table.duplicated(["kc_id", "misconception_id"]).any():
        raise ValueError("중복 KC–오개념 연결")

    kc_dict.to_csv(paths.DICTIONARY / "KC.csv", index=False, encoding="utf-8-sig")
    mc_table.to_csv(paths.DICTIONARY / "오개념.csv", index=False, encoding="utf-8-sig")
    print(f"KC {len(kc_dict)} (Eedi {len(kc_rows)}, 초안 {len(gap)})")
    print(f"오개념 {mc_table.misconception_id.nunique()}개, KC–오개념 연결 {len(mc_table)}행 "
          f"(매핑 후보 {mc_table.use_in_mapping.sum()}, 제외 {(mc_table.use_in_mapping == 0).sum()})")


if __name__ == "__main__":
    main()
