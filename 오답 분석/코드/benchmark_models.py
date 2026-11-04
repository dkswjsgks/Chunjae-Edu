"""여러 모델로 같은 문항 N개를 분석해 비용·성능을 비교한다. 전체 실행 전 모델 선정용.

사용 예 (레포 루트에서):
    python "오답 분석/코드/benchmark_models.py" --dry-run          # 비교 문항 선정과 예상 입력량만 확인
    python "오답 분석/코드/benchmark_models.py"                    # .env의 BENCHMARK_MODELS로 실행
    python "오답 분석/코드/benchmark_models.py" --models gpt-6.1-sol:medium gpt-6-luna:low --n 10

같은 --output 폴더로 다시 실행하면 이미 성공한 (모델, 문항)은 다시 호출하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_errors as ae  # noqa: E402

PRICE_FILE = ae.CODE_DIR / "model_prices.json"
DEFAULT_MODELS = "gpt-6.1-sol:medium,gpt-6-luna:medium,gpt-5.4-mini:medium,gpt-5-mini:medium"

SELECTION_OUT = "비교 대상 문항.csv"
SUMMARY_OUT = "모델별 비용·성능 요약.csv"
ITEM_OUT = "모델별 문항 실행 기록.csv"
REVIEW_OUT = "오답 패턴별 모델 비교_검수표.csv"
STEPS_OUT = "풀이 단계 비교.csv"
REPORT_OUT = "모델 비교 결과.json"
XLSX_OUT = "모델 비교 결과.xlsx"


# ---------------------------------------------------------------- 설정

def parse_models(specs: list[str]) -> list[tuple[str, str]]:
    """"model:effort" 목록. effort를 비우면("model:") reasoning 파라미터를 보내지 않는다."""
    out = []
    for spec in specs:
        for s in spec.split(","):
            s = s.strip()
            if not s:
                continue
            model, _, effort = s.partition(":")
            out.append((model.strip(), effort.strip() if _ else "medium"))
    return out


def load_prices(path: Path = PRICE_FILE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def cost_usd(usage: dict, price: dict | None) -> float | None:
    if not price:
        return None
    cached = usage.get("cached_input_tokens", 0)
    uncached = usage.get("input_tokens", 0) - cached
    return (uncached * price["input"] + cached * price["cached_input"] + usage.get("output_tokens", 0) * price["output"]) / 1e6


# ---------------------------------------------------------------- 문항 선정

def select_items(jobs: list[dict], patterns_by_item: dict, n: int, seed: int) -> list[tuple[dict, str]]:
    """같은 문항을 모든 모델에 쓴다. 정보량이 있는 문항 중 유형이 고르게 섞이도록 고른다."""
    rng = random.Random(seed)

    def n_patterns(j):
        return len(j["payload"]["wrong_patterns"])

    def has_regrade_correct(j):
        return any(p["regraded_result_counts"].get("correct") for p in j["payload"]["wrong_patterns"])

    pool = [j for j in jobs if n_patterns(j) >= 2]
    rng.shuffle(pool)
    chosen: list[tuple[dict, str]] = []
    used = set()

    def take(pred, reason):
        for j in pool:
            if j["item_id"] not in used and pred(j):
                chosen.append((j, reason))
                used.add(j["item_id"])
                return

    # 반드시 포함할 경우
    take(lambda j: not j["payload"]["explanation_available"], "해설 없음(풀이 단계 직접 생성)")
    take(has_regrade_correct, "원본 N이지만 재채점 정답 포함(possibly_correct 판별)")
    take(lambda j: bool(j["payload"]["quality_flags"]) and j["payload"]["explanation_available"], "품질 표시 있음")
    take(lambda j: n_patterns(j) >= 6, "오답 패턴 6개 이상(긴 출력)")
    take(lambda j: j["payload"]["answer_key"]["mode"] == "unordered", "무순형·복수선택")
    take(lambda j: j["image"] is not None, "이미지 첨부")

    # 나머지: 문항형태를 번갈아 가며, 지식이 겹치지 않게
    forms = sorted({j["payload"]["answer_key"]["item_form"] for j in pool})
    knowledge_used = {j["payload"]["taxonomy"].get("지식") for j, _ in chosen}
    i = 0
    while len(chosen) < n and i < len(pool) * 2:
        form = forms[i % len(forms)]
        before = len(chosen)
        take(lambda j: j["payload"]["answer_key"]["item_form"] == form
             and j["payload"]["taxonomy"].get("지식") not in knowledge_used, f"일반({form})")
        if len(chosen) > before:
            knowledge_used.add(chosen[-1][0]["payload"]["taxonomy"].get("지식"))
        i += 1
    while len(chosen) < n:  # 지식 중복을 허용하고 채움
        before = len(chosen)
        take(lambda j: True, "일반")
        if len(chosen) == before:
            break
    return chosen[:n]


# ---------------------------------------------------------------- 실행

def run_model(client, cfg: ae.Config, jobs: list[dict], raw_path: Path) -> dict[str, dict]:
    records = ae.read_raw(raw_path)
    todo = [j for j in jobs if not (records.get(j["item_id"], {}).get("status") == "ok"
                                    and records[j["item_id"]].get("cache_key") == j["cache_key"])]
    if not todo:
        return records
    with open(raw_path, "a", encoding="utf-8") as f, ThreadPoolExecutor(cfg.concurrency) as pool:
        for j, out in zip(todo, pool.map(lambda j: ae.analyze_item(client, cfg, j), todo)):
            rec = {
                "item_id": j["item_id"], "cache_key": j["cache_key"], "model": cfg.model,
                "reasoning_effort": cfg.reasoning_effort, "prompt_version": ae.PROMPT_VERSION,
                "image_attached": j["image"] is not None, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), **out,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            records[j["item_id"]] = rec
            msg = "ok" if out["status"] == "ok" else f"실패: {out['error'][:120]}"
            print(f"  {cfg.model} {j['item_id']} {msg} ({out['latency_sec']}s, 시도 {out['attempts']})", flush=True)
    return records


def job_with_model(job: dict, cfg: ae.Config) -> dict:
    return {**job, "cache_key": ae.cache_key(cfg, job["user_text"], job["image"])}


# ---------------------------------------------------------------- 집계

def summarize(models, jobs, all_records, prices, full_jobs) -> tuple[list[dict], list[dict]]:
    sample_chars = sum(len(j["user_text"]) for j in jobs) or 1
    full_chars = sum(len(j["user_text"]) for j in full_jobs)
    scale = full_chars / sample_chars
    summary_rows, item_rows = [], []
    for model, effort in models:
        key = f"{model}:{effort}"
        recs = [all_records[key].get(j["item_id"]) for j in jobs]
        recs = [r for r in recs if r and r.get("prompt_version") == ae.PROMPT_VERSION]
        ok = [r for r in recs if r["status"] == "ok"]
        usage = Counter()
        for r in recs:
            usage.update(r.get("usage", {}))
        cost = cost_usd(usage, prices.get(model))
        analyses = [a for r in ok for a in r["result"]["pattern_analyses"]]
        cats = Counter(a["error_category"] for a in analyses)
        confs = Counter(a["confidence"] for a in analyses)
        latencies = [r["latency_sec"] for r in recs if "latency_sec" in r]
        n_pat = len(analyses) or 1
        for r in recs:
            u = r.get("usage", {})
            c = cost_usd(u, prices.get(model))
            item_rows.append({
                "model": model, "reasoning_effort": effort, "item_id": r["item_id"], "status": r["status"],
                "attempts": r["attempts"], "attempt_errors": ae.canonical(r.get("attempt_errors", [])),
                "latency_sec": r.get("latency_sec", ""),
                **{k: u.get(k, 0) for k in ae.USAGE_FIELDS},
                "cost_usd": round(c, 6) if c is not None else "",
                "n_patterns": len(r["result"]["pattern_analyses"]) if r["status"] == "ok" else "",
                "step_source": r["result"]["step_source"] if r["status"] == "ok" else "",
            })
        summary_rows.append({
            "model": model, "reasoning_effort": effort,
            "items_ok": len(ok), "items_failed": len(recs) - len(ok), "items_missing": len(jobs) - len(recs),
            "first_try_pass_rate": round(sum(r["attempts"] == 1 for r in ok) / len(recs), 3) if recs else "",
            "patterns_analyzed": len(analyses),
            **{f"total_{k}": usage.get(k, 0) for k in ae.USAGE_FIELDS},
            "total_cost_usd": round(cost, 4) if cost is not None else "가격 없음",
            "cost_per_item_usd": round(cost / len(recs), 5) if cost is not None and recs else "",
            "cost_per_pattern_usd": round(cost / n_pat, 5) if cost is not None else "",
            "est_full_run_usd": round(cost * scale, 2) if cost is not None and len(recs) == len(jobs) else "",
            "latency_mean_sec": round(statistics.mean(latencies), 1) if latencies else "",
            "latency_max_sec": max(latencies) if latencies else "",
            "indeterminate_rate": round(cats["indeterminate"] / n_pat, 3),
            "low_confidence_rate": round(confs["low"] / n_pat, 3),
            "wrong_step_null_rate": round(sum(a["wrong_step"] is None for a in analyses) / n_pat, 3),
            "avg_concepts_per_item": round(statistics.mean(len(r["result"]["required_concepts"]) for r in ok), 2) if ok else "",
            "category_counts": ae.canonical(dict(cats.most_common())),
        })
    return summary_rows, item_rows


def review_rows(models, jobs, all_records, patterns_by_item, selection_reason) -> tuple[list[dict], list[dict], dict]:
    rows, step_rows = [], []
    agree = Counter()
    total = Counter()
    keys = [f"{m}:{e}" for m, e in models]
    for j in jobs:
        item_id = j["item_id"]
        per_model = {}
        for k in keys:
            r = all_records[k].get(item_id)
            if r and r["status"] == "ok" and r.get("prompt_version") == ae.PROMPT_VERSION:
                per_model[k] = r["result"]
                step_rows.append({
                    "item_id": item_id, "model": k, "step_source": r["result"]["step_source"],
                    "solution_steps": "\n".join(f"{i}. {s}" for i, s in enumerate(r["result"]["solution_steps"], 1)),
                    "required_concepts": "\n".join(f"{c['concept_id']} {c['name']}" for c in r["result"]["required_concepts"]),
                    "item_quality_note": r["result"]["item_quality_note"],
                })
        for p in j["payload"]["wrong_patterns"]:
            row = {
                "item_id": item_id, "선정 이유": selection_reason[item_id],
                "지식": j["payload"]["taxonomy"].get("지식", ""),
                "문제": j["payload"]["question"].get("text", "")[:300],
                "정답": ae.canonical(j["payload"]["answer_key"]["expected_vectors"]),
                "pattern_id": p["pattern_id"], "응답": ae.canonical(p["response_tokens"]),
                "칸별 채점": ae.canonical(p["blank_marks"]), "응답 수": p["count"],
            }
            cats = {}
            for k in keys:
                res = per_model.get(k)
                a = next((x for x in res["pattern_analyses"] if x["pattern_id"] == p["pattern_id"]), None) if res else None
                concepts = {c["concept_id"]: c["name"] for c in res["required_concepts"]} if res else {}
                if a:
                    cats[k] = a["error_category"]
                row[f"{k} | 유형"] = a["error_category"] if a else ""
                row[f"{k} | 신뢰도"] = a["confidence"] if a else ""
                row[f"{k} | 개념"] = ", ".join(concepts.get(c, c) for c in a["concept_ids"]) if a else ""
                row[f"{k} | 오개념"] = a["misconception"] if a else ""
                row[f"{k} | 추정 풀이"] = a["inferred_solution_path"] if a else ""
                row[f"{k} | 점수(1~5)"] = ""
            row["모델 간 유형 일치"] = int(len(set(cats.values())) == 1) if len(cats) == len(keys) else ""
            for a_key, b_key in combinations(keys, 2):
                if a_key in cats and b_key in cats:
                    total[(a_key, b_key)] += 1
                    agree[(a_key, b_key)] += cats[a_key] == cats[b_key]
            row["검수_가장 타당한 모델"] = ""
            row["검수_메모"] = ""
            rows.append(row)
    agreement = {f"{a} vs {b}": round(agree[(a, b)] / total[(a, b)], 3) for a, b in total}
    return rows, step_rows, agreement


# ---------------------------------------------------------------- main

def main(argv=None, client_factory=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", help='"모델:추론강도" 목록. 기본은 .env의 BENCHMARK_MODELS')
    ap.add_argument("--n", type=int, help="모델별 문항 수(기본 BENCHMARK_N_ITEMS 또는 10)")
    ap.add_argument("--seed", type=int, default=20261103)
    ap.add_argument("--items", nargs="*", help="자동 선정 대신 지정할 item_id")
    ap.add_argument("--input", type=Path, default=ae.PREP_DIR)
    ap.add_argument("--output", type=Path, help="결과 폴더(기본: 분석 결과/모델 비교/<시각>)")
    ap.add_argument("--env", type=Path, default=ae.REPO_ROOT / ".env")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--export-only", action="store_true",
                    help="API 호출 없이 --output 폴더에 저장된 응답으로 CSV·엑셀만 다시 생성")
    args = ap.parse_args(argv)

    ae.load_dotenv(args.env)
    import os
    models = parse_models(args.models or [os.environ.get("BENCHMARK_MODELS") or DEFAULT_MODELS])
    n = args.n or int(os.environ.get("BENCHMARK_N_ITEMS", "10"))
    prices = load_prices()
    base_cfg = ae.Config()

    packets = ae.load_packets(args.input)
    patterns_by_item = ae.load_wrong_patterns(args.input)
    full_jobs = ae.build_jobs(packets, patterns_by_item, base_cfg)
    if args.items:
        by_id = {j["item_id"]: j for j in full_jobs}
        missing = [i for i in args.items if i not in by_id]
        if missing:
            print(f"분석 대상이 아닌 item_id: {missing}", file=sys.stderr)
            return 2
        selected = [(by_id[i], "지정") for i in args.items]
    else:
        selected = select_items(full_jobs, patterns_by_item, n, args.seed)
    jobs = [j for j, _ in selected]
    reason = {j["item_id"]: r for j, r in selected}

    out_dir = args.output or (ae.DEFAULT_OUTPUT / "모델 비교" / time.strftime("%Y%m%d-%H%M"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ae.write_csv(out_dir / SELECTION_OUT, [{
        "item_id": j["item_id"], "선정 이유": reason[j["item_id"]],
        "item_form": j["payload"]["answer_key"]["item_form"], "지식": j["payload"]["taxonomy"].get("지식", ""),
        "오답 패턴 수": len(j["payload"]["wrong_patterns"]),
        "오답 응답 수": sum(p["count"] for p in j["payload"]["wrong_patterns"]),
        "해설 있음": int(j["payload"]["explanation_available"]), "이미지 첨부": int(j["image"] is not None),
        "입력 글자 수": len(j["user_text"]),
    } for j in jobs])

    missing_price = [m for m, _ in models if m not in prices]
    print(f"모델: {', '.join(f'{m}({e or '미지정'})' for m, e in models)}")
    print(f"문항 {len(jobs)}개, 오답 패턴 {sum(len(j['payload']['wrong_patterns']) for j in jobs)}개 -> {out_dir}")
    if missing_price:
        print(f"[경고] model_prices.json에 가격 없음: {missing_price} (비용은 '가격 없음'으로 표시)")
    if args.dry_run:
        for j, r in selected:
            print(f"  {j['item_id']}  {r}  패턴 {len(j['payload']['wrong_patterns'])}개")
        return 0

    if args.export_only:
        if not args.output:
            print("--export-only에는 결과 폴더(--output)가 필요합니다.", file=sys.stderr)
            return 2
        client_factory = lambda: None  # noqa: E731
    if client_factory is None:
        if not base_cfg.api_key:
            print("OPENAI_API_KEY가 없습니다. 레포 루트 .env에 설정하세요.", file=sys.stderr)
            return 2
        from openai import OpenAI

        def client_factory():
            return OpenAI(api_key=base_cfg.api_key, base_url=base_cfg.base_url, max_retries=5, timeout=300)

    client = client_factory()
    all_records = {}
    for model, effort in models:
        cfg = ae.Config()
        cfg.model, cfg.reasoning_effort = model, effort
        model_jobs = [job_with_model(j, cfg) for j in jobs]
        safe = f"{model}_{effort or 'none'}".replace("/", "_").replace(":", "_")
        raw_path = out_dir / f"{safe}_응답.jsonl"
        if args.export_only:
            all_records[f"{model}:{effort}"] = ae.read_raw(raw_path)
        else:
            print(f"[{model} / {effort or '미지정'}]")
            all_records[f"{model}:{effort}"] = run_model(client, cfg, model_jobs, raw_path)

    summary_rows, item_rows = summarize(models, jobs, all_records, prices, full_jobs)
    rows, step_rows, agreement = review_rows(models, jobs, all_records, patterns_by_item, reason)
    ae.write_csv(out_dir / SUMMARY_OUT, summary_rows)
    ae.write_csv(out_dir / ITEM_OUT, item_rows)
    ae.write_csv(out_dir / REVIEW_OUT, rows)
    ae.write_csv(out_dir / STEPS_OUT, step_rows)
    (out_dir / REPORT_OUT).write_text(json.dumps({
        "prompt_version": ae.PROMPT_VERSION, "models": [f"{m}:{e}" for m, e in models],
        "items": [j["item_id"] for j in jobs], "full_run_items": len(full_jobs),
        "full_run_estimate_basis": "표본 비용 × (전체 입력 글자 수 / 표본 입력 글자 수). 출력 길이는 오답 패턴 수에 비례하므로 근사치",
        "category_agreement": agreement, "summary": summary_rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n모델                    성공  비용(USD)  문항당     전체 예상   평균 지연")
    for s in summary_rows:
        print(f"{s['model']:<22}{s['items_ok']:>3}/{len(jobs):<3}{str(s['total_cost_usd']):>10} "
              f"{str(s['cost_per_item_usd']):>9} {str(s['est_full_run_usd']):>10} {str(s['latency_mean_sec']):>8}s")
    print(f"유형 일치율: {agreement}")
    from excel_report import write_report

    xlsx = write_report(out_dir / XLSX_OUT, models, jobs, all_records, summary_rows, prices, len(full_jobs))
    print(f"엑셀: {xlsx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
