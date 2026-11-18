"""공통 설정. 값만 두고 로직은 두지 않는다.

외부 데이터(원본 CSV, 추가 데이터 2종)는 레포에 올리지 않는다. 각자 PC의 위치를
레포 루트 .env(형식은 .env.example)에 적는다. LLM 모델·키도 .env에 둔다.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 파이프라인 1차 대상 지식 5개 (지식 단위 이름은 전처리 분류표의 name과 같다)
TARGET_KNOWLEDGE = [
    "유리수의 덧셈과 뺄셈의 혼합계산",
    "정수와 유리수의 대소 관계",
    "정수와 유리수의 덧셈",
    "정수와 유리수의 뺄셈",
    "정수와 유리수의 대소 관계의 활용",
]

# 첫 실험 대상 지식 2개
FIRST_EXPERIMENT_KNOWLEDGE = TARGET_KNOWLEDGE[:2]

# 별도 제공 원본(문항_샘플.csv, 문제 이미지)이 있는 폴더. 전처리 코드와 같은 변수
RAW_ROOT = os.environ.get("CHUNJAE_RAW_ROOT")

# 추가 데이터 2종이 있는 폴더
#   1. 학습자 풀이 이력(아이디 난수화+맞힐 확률 추가).csv  (CP949)
#   2. T샘 족보(아이디 난수화).csv                          (UTF-8 BOM)
EXTRA_ROOT = os.environ.get("CHUNJAE_EXTRA_ROOT")
KT_PROB_FILE = "1. 학습자 풀이 이력(아이디 난수화+맞힐 확률 추가).csv"
TSAM_FILE = "2. T샘 족보(아이디 난수화).csv"

SEED = 20261118

# 2단계 1_build_option_table.py: 단답형 오답값을 선지 행으로 만들 최소 학생 수
MIN_SHORT_ANSWER_COUNT = 2

# 2단계 3_버전2_확률: 선지마다 남길 오개념 후보 수
TOP_N_MISCONCEPTIONS = 10
