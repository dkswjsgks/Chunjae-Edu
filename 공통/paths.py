"""레포 안 경로 상수. 폴더 이름을 바꾸면 여기만 고친다."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREPROCESSED = REPO / "데이터 전처리" / "전처리 결과"      # 원본 전처리 산출물(검토·추적용 포함). 고치지 않는다
ANALYSIS_DATA = REPO / "분석 데이터"                      # 0단계가 만든 조인 테이블. 파이프라인은 여기를 읽는다
DICTIONARY = REPO / "사전"
EEDI = REPO / "외부 자료" / "Eedi"
EXPERIMENT_LOG = REPO / "실험 기록"

STAGE0 = REPO / "0단계 데이터"
STAGE1 = REPO / "1단계 사전"
STAGE2 = REPO / "2단계 Q행렬"
STAGE3 = REPO / "3단계 검증"
STAGE4 = REPO / "4단계 프로파일"
STAGE5 = REPO / "5단계 조언"
STAGE6 = REPO / "6단계 평가"

# 확정된 Q행렬(3단계 3_evaluate_q.py가 복사). 4단계 이후는 여기만 읽는다
CONFIRMED_Q = STAGE3 / "결과" / "확정"
