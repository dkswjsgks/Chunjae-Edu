"""
[2단계 Q행렬 / 1 선지표] Q행렬의 행(문항-선지)을 만든다. LLM을 쓰지 않는다.

실행 (레포 루트에서):  python "2단계 Q행렬/1_build_option_table.py"

입력: 분석 데이터/문항.csv, 풀이.csv, 빈칸응답.csv
출력: 2단계 Q행렬/결과/<실행ID>/선지표.csv
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "공통"))

import data_io  # noqa: E402
import paths  # noqa: E402
import settings  # noqa: E402

# ── 분석 설정. 명령줄 --키 값으로 바꿀 수 있다 ─────────────────────────
PARAMS = {
    "min_short_answer_count": settings.MIN_SHORT_ANSWER_COUNT,   # 단답 오답값을 선지 행으로 만들 최소 학생 수
    "knowledge": settings.FIRST_EXPERIMENT_KNOWLEDGE,
}

def choice_rows(items, attempts):
    """
    객관식: 선지마다 한 행 (option_row_id=<item_id>:<선지번호>, option_type=객관식선지/정답, option_value, is_correct, n_chosen)
    선택 학생 0명인 선지도 남긴다
    """
    raise NotImplementedError("choice_rows: 아직 구현하지 않았다")


def short_answer_rows(items, attempts, blanks, min_count):
    """
    단답: response_normalized 기준 오답값 중 min_count명 이상만 행으로 (option_type=단답오답값)
    나머지는 "<item_id>:기타" 한 행. 여러 칸이면 칸 단위 오답값. 전체 미응답은 행으로 만들지 않는다
    """
    raise NotImplementedError("short_answer_rows: 아직 구현하지 않았다")


def mark_excluded(rows, items):
    """
    기준 정답이 확정되지 않은 문항(blocked_source_defect, unresolved)은 excluded=1
    """
    raise NotImplementedError("mark_excluded: 아직 구현하지 않았다")


def main():
    cfg = data_io.parse_config(PARAMS)
    run = data_io.new_run(HERE, "2-1-선지표", cfg)
    items, attempts = data_io.load_items(cfg["knowledge"]), data_io.load_attempts(cfg["knowledge"])
    rows = choice_rows(items, attempts) + short_answer_rows(items, attempts, data_io.load_blank_responses(),
                                                            cfg["min_short_answer_count"])
    import pandas as pd  # noqa: E402
    pd.DataFrame(mark_excluded(rows, items)).to_csv(run.dir / "선지표.csv", index=False, encoding="utf-8-sig")
    data_io.finish_run(run)


if __name__ == "__main__":
    main()
