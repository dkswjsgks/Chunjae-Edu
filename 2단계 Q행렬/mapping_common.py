"""
[2단계 Q행렬 / 공통] 세 버전의 run.py가 함께 쓰는 입력·후보·검사·변환 함수.

  행 단위: 문항-선지 (정답 선지 포함, 단답형은 자주 나온 오답값)
  후보 KC: 2_문항KC배정 결과에서 그 문항에 배정된 KC
  후보 오개념: 후보 KC에 연결된 오개념(사전/오개념.csv에서 kc_id가 후보 KC이고 use_in_mapping=1인 행)

함수: load_inputs, kc_candidates, misconception_candidates, item_vars, reproduces, check_kc_subset, to_wide
"""

import ast
import operator
import re
import sys
from fractions import Fraction
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "공통"))

import data_io  # noqa: E402
import paths  # noqa: E402


ITEM_KC_DIR = paths.STAGE2 / "2_문항KC배정"


def _latest_by_date(stage_dir, method):
    """실행 ID 끝의 <날짜>-<순번>으로 가장 최근 폴더. latest_run은 이름순이라 provider가 섞이면 날짜를 무시한다"""
    runs = list((Path(stage_dir) / "결과").glob(f"{method}-*"))
    if not runs:
        raise FileNotFoundError(f"{stage_dir}/결과/{method}-* 실행 결과가 없다. 먼저 그 단계를 실행한다")
    return max(runs, key=lambda d: d.name.rsplit("-", 2)[-2:])


def load_inputs(cfg):
    """
    돌려줄 dict:
      options   선지표.csv에서 excluded=0인 행 (option_row_id, item_id, option_value, is_correct, n_chosen, wrong_share)
      item_kc   2_문항KC배정의 문항_KC.csv (cfg["kc_size"] 버전)
      kc, mc          사전/KC.csv, 사전/오개념.csv (오개념의 지식은 mc.kc_id → kc.knowledge_id로 찾는다)
      packets   data_io.load_item_packets()
    cfg["option_table_run"], cfg["item_kc_run"]이 None이면 data_io.latest_run으로 가장 최근 결과를 쓴다
    "기타" 행(드문 단답 오답을 묶은 행)은 진단할 값이 없어 options에서 뺀다
    문항_KC.csv는 원래 KC 하나뿐이다. kc_size=group은 kc_candidates가 kc_group으로 묶는다
    """
    opt_dir = (paths.STAGE2 / "결과" / cfg["option_table_run"] if cfg.get("option_table_run")
               else data_io.latest_run(paths.STAGE2, "2-1-선지표"))
    kc_dir = (ITEM_KC_DIR / "결과" / cfg["item_kc_run"] if cfg.get("item_kc_run")
              else _latest_by_date(ITEM_KC_DIR, "2-2-KC배정"))
    items = set(data_io.load_items(cfg.get("knowledge")).item_id)
    options = data_io._csv(opt_dir / "선지표.csv")
    options = options[(options.excluded == "0") & (options.option_type != "기타") & options.item_id.isin(items)]
    item_kc = data_io._csv(kc_dir / "문항_KC.csv")
    item_kc = item_kc[(item_kc.kc_id != "") & item_kc.item_id.isin(items)]
    return {"options": options.reset_index(drop=True), "item_kc": item_kc,
            "kc": data_io.load_dictionary("KC"), "mc": data_io.load_dictionary("오개념"),
            "packets": data_io.load_item_packets(set(options.item_id)),
            "item_knowledge": dict(zip(*data_io.load_items(cfg.get("knowledge"))[["item_id", "knowledge_id"]].values.T)),
            "sources": {"option_table_run": opt_dir.name, "item_kc_run": kc_dir.name}}


def _item_kcs(item_id, inputs):
    """그 문항에 배정된 원래 KC ID (풀이 단계 순서, 중복 제거)"""
    return list(dict.fromkeys(inputs["item_kc"].loc[inputs["item_kc"].item_id == item_id, "kc_id"]))


def kc_candidates(item_id, inputs, cfg):
    """
    그 문항에 배정된 KC → ("KC ID | 이름" 줄을 이은 문자열, ID 목록)
    kc_size=group이면 kc_group 단위로 묶어 묶음 ID와 이름을 쓴다
    """
    kc = inputs["kc"].set_index("kc_id")
    ids = [k for k in _item_kcs(item_id, inputs) if k in kc.index]
    if cfg.get("kc_size") == "group":
        names = dict(zip(kc.loc[ids, "kc_group"], kc.loc[ids, "kc_group_name"]))
    else:
        names = dict(zip(ids, kc.loc[ids, "kc_name_ko"]))
    return "\n".join(f"{k} | {v}" for k, v in names.items()), list(names)


def misconception_candidates(item_id, kc_ids, inputs, cfg):
    """
    candidate_scope=item_kc: kc_ids에 연결된 오개념
    candidate_scope=knowledge: 그 문항 지식의 매핑 후보 오개념 전체
    → ("ID | 한국어 이름 | 원문" 줄을 이은 문자열, ID 목록). 사전에 오개념 정의 열이 아직 없어 정의는 넣지 않는다
    매핑 후보는 use_in_mapping=1(관련도 상·중)만. 같은 오개념이 여러 KC에 걸치면 한 번만 넣는다
    """
    kc, m = inputs["kc"], inputs["mc"]
    m = m[m.use_in_mapping == "1"]
    if cfg.get("candidate_scope") == "knowledge":
        kcs = set(kc.loc[kc.knowledge_id == inputs["item_knowledge"].get(item_id), "kc_id"])
    elif cfg.get("kc_size") == "group":   # 묶음 ID → 이 문항에 배정된 원래 KC 중 그 묶음에 속한 것
        group = dict(zip(kc.kc_id, kc.kc_group))
        kcs = {k for k in _item_kcs(item_id, inputs) if group.get(k) in set(kc_ids)}
    else:
        kcs = set(kc_ids)
    m = m[m.kc_id.isin(kcs)].drop_duplicates("misconception_id")
    return "\n".join(f"{r.misconception_id} | {r.name_ko} | {r.name_en}" for r in m.itertuples()), \
        list(m.misconception_id)


def _with_image(text, description):
    return f"{text}\n[그림 설명] {description}" if description else text


def item_vars(packet, option_row):
    """
    프롬프트 변수: question(문제 + 이미지 설명), options("① -3" 줄), answer, explanation,
    target_option(진단할 선지 또는 오답값), is_correct("정답"/"오답"), n_chosen, wrong_share(오답 중 %)
    학생 ID와 개별 풀이 기록은 넣지 않는다
    """
    q, e, key = packet["question"], packet["explanation"], packet["answer_key"]
    choices = {o["option_id"]: o["text"] for o in q.get("options") or []}
    if choices:
        answer = ", ".join(f"{t} {choices.get(t, '')}".strip() for v in key["expected_vectors"] for t in v)
        target = f"{option_row.option_label} {option_row.option_value}"
    else:
        answer = " 또는 ".join(", ".join(v) for v in key["expected_vectors"])
        blank = str(getattr(option_row, "blank_index", "") or "")
        target = (f"{blank}번째 칸에 {option_row.option_value}" if blank else option_row.option_value)
    correct = str(option_row.is_correct) == "1"
    return {"question": _with_image(q["text"], q.get("image_description")),
            "options": "\n".join(f"{k} {v}" for k, v in choices.items()) or "(단답형: 선지 없음)",
            "answer": answer,
            "explanation": _with_image(e.get("text") or "(해설 없음)", e.get("image_description")),
            "target_option": target, "is_correct": "정답" if correct else "오답",
            "n_chosen": str(option_row.n_chosen), "wrong_share": str(option_row.wrong_share) if not correct else "-"}


# ---------------------------------------------------------------- 검사
def check_kc_subset(rows):
    """
    rows: option_row_id, item_id, is_correct("1"/"0"), kc_ids(";" 구분) 열이 있는 DataFrame
    오답 선지의 KC가 같은 문항 정답 선지의 KC 안에 있는지 kc_subset_ok(True/False) 열을 붙인다
    """
    rows = rows.copy()
    key = rows[rows.is_correct.astype(str) == "1"].groupby("item_id").kc_ids.agg(
        lambda s: set(";".join(s).split(";")) - {""})
    rows["kc_subset_ok"] = [
        True if str(r.is_correct) == "1" else (set(r.kc_ids.split(";")) - {""}) <= key.get(r.item_id, set())
        for r in rows.itertuples()]
    return rows


def to_wide(long, fill):
    """long: option_row_id, attribute_id, value → 행 option_row_id, 열 attribute_id(KC 먼저, 오개념 다음)"""
    wide = long.pivot_table(index="option_row_id", columns="attribute_id", values="value", aggfunc="first")
    cols = sorted(c for c in wide.columns if str(c).startswith("KC")) + \
        sorted(c for c in wide.columns if not str(c).startswith("KC"))
    tidy = lambda v: int(v) if isinstance(v, float) and v.is_integer() else v
    return wide[cols].apply(lambda col: col.map(tidy)).fillna(fill)


# ---------------------------------------------------------------- 계산 경로 재계산
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    raise ValueError("계산식이 아니다")


def to_value(text):
    s = str(text).strip().replace("×", "*").replace("÷", "/").replace("−", "-").replace(" ", "")
    if not s or not re.fullmatch(r"[0-9+\-*/().]+", s):
        return None
    try:
        return _eval(ast.parse(s, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError):
        return None


def reproduces(trace, option_value):
    """
    계산 경로의 마지막 "식 = 값" 줄의 왼쪽 식을 분수로 계산해 선지 값과 비교한다.
    True/False, 계산식이 아니면(대소 비교, 선지 번호 등) None. 약분 전후·소수 표기는 같은 값으로 본다.
      reproduces("(-2/3)+(1/2) = -1/6", "-1/6") → True
    """
    lines = [l for l in str(trace).splitlines() if "=" in l]
    if not lines:
        return None
    got, want = to_value(lines[-1].split("=")[0]), to_value(option_value)
    if got is None or want is None:
        return None
    return got == want
