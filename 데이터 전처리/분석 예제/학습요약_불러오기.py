"""외부 패키지 없이 전처리 결과를 읽는 예제. 학생 유형을 임의로 분류하지 않는다."""
import csv
import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def load_learning_summary():
    path = PACKAGE_ROOT / '전처리 결과' / '학생별 지식_학습 요약.csv'
    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    identifiers = {'학생ID', '지식ID', '지식명', '학년', '학기', '집계범위',
                   '최초_시험완료일시', '최종_시험완료일시', '난이도별_관측통계'}
    for row in rows:
        for name, value in row.items():
            if name in identifiers:
                continue
            if name.endswith('률'):
                row[name] = float(value) if value else None
            else:
                row[name] = int(value)
        row['난이도별_관측통계'] = json.loads(row['난이도별_관측통계'])
    return rows


def load_attempts():
    path = PACKAGE_ROOT / '전처리 결과' / '학습자 풀이 이력_전처리.csv'
    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row['response_normalized'] = json.loads(row['response_normalized'])
        row['analysis_cautions'] = json.loads(row['analysis_cautions'])
    return rows


if __name__ == '__main__':
    summaries = load_learning_summary()
    attempts = load_attempts()
    print('학생 수:', len({row['학생ID'] for row in summaries}))
    print('학생·지식 조합 수:', len(summaries))
    print('전체 풀이 이력 수:', len(attempts))
    print('원본 Y/N이 있는 풀이 수:', sum(row['source_correctness'] in {'Y', 'N'} for row in attempts))
    print('재풀이 기록 수:', sum(int(row['is_repeat_item']) for row in attempts))
    print('주의사항이 있는 풀이 수:', sum(bool(row['analysis_cautions']) for row in attempts))
    print('이 요약은 제공된 전체 기간의 관측값이며, KT 성취도나 오답 원인 진단 결과가 아닙니다.')
