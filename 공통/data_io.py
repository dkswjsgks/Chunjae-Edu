"""
데이터 읽기, 실행 설정(CONFIG) 파싱, 실험 기록을 한곳에 모은다.

  load_*()                 분석 데이터·사전·문항 입력자료·추가 데이터 읽기 (ID 열은 문자열)
  parse_config(CONFIG)     run.py의 CONFIG 값을 명령줄 --키 값으로 덮어쓴다
  new_run(stage_dir, method, config)   결과/<실행ID>/ 폴더와 config.json을 만든다
  finish_run(run, metrics, note)       실험 기록/실험_목록.csv에 한 줄 남긴다
  latest_run(stage_dir, method)        가장 최근 실행 폴더
"""

import argparse
import csv
import datetime as dt
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import paths
import settings


def _csv(path):
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def knowledge_ids(names=None):
    kd = load_dictionary("지식")
    names = names or settings.FIRST_EXPERIMENT_KNOWLEDGE
    return set(kd.loc[kd.knowledge_name.isin(names), "knowledge_id"])


def load_topics():
    """분석 데이터/토픽.csv: 토픽 하나당 한 행(토픽·지식·단원 이름)"""
    return _csv(paths.ANALYSIS_DATA / "토픽.csv")


def load_items(knowledge=None):
    """분석 데이터/문항.csv: 문항 하나당 한 행(분류 이름, 내용, 정답키, 품질 표시). knowledge=False면 전체"""
    df = _csv(paths.ANALYSIS_DATA / "문항.csv")
    return df[df.knowledge_id.isin(knowledge_ids(knowledge))] if knowledge is not False else df


def load_attempts(knowledge=None):
    """분석 데이터/풀이.csv: 학생 응답 하나당 한 행. knowledge=False면 전체"""
    df = _csv(paths.ANALYSIS_DATA / "풀이.csv")
    return df[df.knowledge_id.isin(knowledge_ids(knowledge))] if knowledge is not False else df


def load_blank_responses():
    """분석 데이터/빈칸응답.csv: 응답의 입력칸(또는 선택 토큰) 하나당 한 행"""
    return _csv(paths.ANALYSIS_DATA / "빈칸응답.csv")


def load_item_packets(item_ids=None):
    """전처리 결과의 문항별 LLM 입력자료(jsonl). 정답·전 기간 오답 분포 포함, 학생 공개·과거시점 예측 입력 금지"""
    out = {}
    with open(paths.PREPROCESSED / "문항별 인공지능 분석_입력자료.jsonl", encoding="utf-8-sig") as f:
        for line in f:
            r = json.loads(line)
            if item_ids is None or r["item_id"] in item_ids:
                out[r["item_id"]] = r
    return out


def load_dictionary(name):
    return _csv(paths.DICTIONARY / f"{name}.csv")


def load_kt_prob():
    """추가 데이터 1. 정답확률이 있는 행만. 완료일시 열은 손상되어 쓰지 않는다."""
    if not settings.EXTRA_ROOT:
        raise RuntimeError("환경변수 CHUNJAE_EXTRA_ROOT를 지정한다")
    df = pd.read_csv(Path(settings.EXTRA_ROOT) / settings.KT_PROB_FILE, encoding="cp949", dtype=str)
    return df[df["정답확률"].notna()]


# ---------------------------------------------------------------- 실행 설정
def parse_config(config):
    p = argparse.ArgumentParser()
    for k, v in config.items():
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            p.add_argument(flag, type=lambda s: s.lower() in ("1", "true", "yes"), default=v)
        elif isinstance(v, (int, float)) and v is not None:
            p.add_argument(flag, type=type(v), default=v)
        elif isinstance(v, list):
            p.add_argument(flag, nargs="+", default=v)
        else:
            p.add_argument(flag, default=v)
    return vars(p.parse_args())


# ---------------------------------------------------------------- 실험 기록
def new_run(stage_dir, method, config):
    stage_dir = Path(stage_dir)
    today = dt.date.today().strftime("%Y%m%d")
    base = stage_dir / "결과"
    base.mkdir(parents=True, exist_ok=True)
    n = 1 + sum(1 for d in base.glob(f"{method}-{today}-*"))
    run_id = f"{method}-{today}-{n:02d}"
    d = base / run_id
    d.mkdir()
    (d / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return SimpleNamespace(id=run_id, dir=d, cache=d / "_cache", method=method, config=config,
                           started=dt.datetime.now().isoformat(timespec="seconds"))


def finish_run(run, metrics=None, note=""):
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                cwd=paths.REPO).stdout.strip()
    except OSError:
        commit = ""
    row = {"run_id": run.id, "stage": run.method.split("-")[0], "method": run.method,
           "knowledge_scope": ";".join(run.config.get("knowledge", []) or []),
           "started_at": run.started, "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
           "owner": "", "code_commit": commit, "input_hash": "",
           "llm_model": f"{run.config.get('provider', '')}:{run.config.get('model') or ''}",
           "key_metrics": json.dumps(metrics or {}, ensure_ascii=False),
           "result_path": str(run.dir.relative_to(paths.REPO)), "status": "done", "note": note}
    log = paths.EXPERIMENT_LOG / "실험_목록.csv"
    with open(log, "a", encoding="utf-8-sig", newline="") as f:
        csv.DictWriter(f, fieldnames=list(row)).writerow(row)


def latest_run(stage_dir, method):
    runs = sorted((Path(stage_dir) / "결과").glob(f"{method}-*"))
    if not runs:
        raise FileNotFoundError(f"{stage_dir}/결과/{method}-* 실행 결과가 없다. 먼저 그 단계를 실행한다")
    return runs[-1]
