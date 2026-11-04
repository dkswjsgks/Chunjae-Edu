"""네트워크 없이 입력 구성·검증·내보내기를 확인한다.
실행(레포 루트): python -m unittest discover -s "오답 분석/코드" -p "test_*.py" -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_errors as ae  # noqa: E402


def fake_result(payload, bad=False):
    pats = payload["wrong_patterns"][: -1 if bad else None]
    return {
        "item_id": payload["item_id"],
        "step_source": "explanation" if payload["explanation_available"] else "generated",
        "solution_steps": ["조건을 부등식으로 쓴다", "범위의 정수를 찾는다"],
        "required_concepts": [{"concept_id": "C1", "name": "부등호", "description": "미만/이상", "is_prerequisite": True}],
        "pattern_analyses": [
            {"pattern_id": p["pattern_id"], "error_category": "misread_question", "concept_ids": ["C1"],
             "inferred_solution_path": "...", "wrong_step": 1, "misconception": "...", "confidence": "low",
             "alternative_explanations": [], "remediation_hint": "..."}
            for p in pats
        ],
        "item_quality_note": "",
    }


class FakeClient:
    def __init__(self, payloads, bad_first=False):
        self.payloads, self.calls, self.bad_first = payloads, 0, bad_first
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls += 1
        assert kw["text"]["format"]["strict"] is True and kw["store"] is False
        text = kw["input"][0]["content"][0]["text"]
        item_id = json.loads(text.split("```json\n", 1)[1].rsplit("\n```", 1)[0])["item_id"]
        out = fake_result(self.payloads[item_id], bad=self.bad_first and self.calls == 1)
        usage = SimpleNamespace(input_tokens=1000, output_tokens=500,
                                input_tokens_details=SimpleNamespace(cached_tokens=200),
                                output_tokens_details=SimpleNamespace(reasoning_tokens=300))
        return SimpleNamespace(id="r", status="completed", output_text=json.dumps(out, ensure_ascii=False), usage=usage)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packets = ae.load_packets(ae.PREP_DIR)
        cls.patterns = ae.load_wrong_patterns(ae.PREP_DIR)
        cls.cfg = ae.Config()
        cls.cfg.attach_images = False
        cls.cfg.reasoning_effort = ""
        cls.cfg.max_attempts = 2
        cls.jobs = ae.build_jobs(cls.packets, cls.patterns, cls.cfg)

    def test_patterns_match_packet_distribution(self):
        for item_id, pats in list(self.patterns.items())[:300]:
            dist = self.packets[item_id]["historical_outcomes"]["wrong_response_distribution"]
            want = {ae.canonical(d["response"]): d["count"] for d in dist}
            got = {ae.canonical(p["response_tokens"]): p["count"] for p in pats}
            self.assertEqual(want, got, item_id)

    def test_no_student_ids_and_skips(self):
        for j in self.jobs:
            self.assertNotIn("student_id", j["user_text"])
            self.assertNotIn(self.packets[j["item_id"]]["answer_key"]["key_status"], ae.SKIP_KEY_STATUS)
            self.assertTrue(all(p["pattern_id"] for p in j["payload"]["wrong_patterns"]))

    def test_validate_catches_missing_pattern(self):
        job = next(j for j in self.jobs if len(j["payload"]["wrong_patterns"]) > 1)
        self.assertEqual(ae.validate_result(fake_result(job["payload"]), job["payload"]), [])
        self.assertTrue(ae.validate_result(fake_result(job["payload"], bad=True), job["payload"]))

    def test_step_source_rule(self):
        with_exp = next(j for j in self.jobs if j["payload"]["explanation_available"])
        without = next(j for j in self.jobs if not j["payload"]["explanation_available"])
        r = fake_result(with_exp["payload"]); r["step_source"] = "generated"
        self.assertTrue(ae.validate_result(r, with_exp["payload"]))
        r = fake_result(without["payload"]); r["step_source"] = "explanation"
        self.assertTrue(ae.validate_result(r, without["payload"]))
        self.assertEqual(ae.validate_result(fake_result(without["payload"]), without["payload"]), [])

    def test_benchmark_end_to_end(self):
        import benchmark_models as bm
        self.assertEqual(bm.parse_models(["a:low,b:", "c"]), [("a", "low"), ("b", ""), ("c", "medium")])
        self.assertAlmostEqual(bm.cost_usd({"input_tokens": 1000, "cached_input_tokens": 200, "output_tokens": 500},
                                           {"input": 2, "cached_input": 0.1, "output": 10}), (800 * 2 + 200 * 0.1 + 5000) / 1e6)
        sel = bm.select_items(self.jobs, self.patterns, 10, 1)
        self.assertEqual(len(sel), 10)
        self.assertEqual(len({j["item_id"] for j, _ in sel}), 10)
        self.assertTrue(any(not j["payload"]["explanation_available"] for j, _ in sel))
        self.assertEqual([j["item_id"] for j, _ in sel], [j["item_id"] for j, _ in bm.select_items(self.jobs, self.patterns, 10, 1)])
        payloads = {j["item_id"]: j["payload"] for j in self.jobs}
        ae.time.sleep = lambda s: None
        client = FakeClient(payloads)
        with tempfile.TemporaryDirectory() as d:
            argv = ["--models", "gpt-6.1-sol:medium,gpt-6-luna:low", "--n", "3", "--output", d, "--env", str(Path(d) / "none")]
            self.assertEqual(bm.main(argv, client_factory=lambda: client), 0)
            self.assertEqual(client.calls, 6)
            self.assertEqual(bm.main(argv, client_factory=lambda: client), 0)
            self.assertEqual(client.calls, 6)  # 재실행 시 캐시 사용
            with open(Path(d) / bm.SUMMARY_OUT, encoding="utf-8-sig") as f:
                rows = list(__import__("csv").DictReader(f))
            self.assertEqual([r["items_ok"] for r in rows], ["3", "3"])
            self.assertAlmostEqual(float(rows[0]["total_cost_usd"]), 3 * (800 * 2 + 200 * 0.1 + 500 * 10) / 1e6, places=4)
            self.assertTrue((Path(d) / bm.REVIEW_OUT).stat().st_size > 0)
            from openpyxl import load_workbook
            (Path(d) / bm.XLSX_OUT).unlink()
            self.assertEqual(bm.main(argv + ["--export-only"]), 0)  # 호출 없이 엑셀 재생성
            self.assertEqual(client.calls, 6)
            wb = load_workbook(Path(d) / bm.XLSX_OUT)
            self.assertEqual(wb.sheetnames, ["오답 판단", "비용"])
            ws = wb["오답 판단"]
            self.assertEqual(ws.cell(row=2, column=6).value, "판단")
            self.assertEqual(ws.cell(row=2, column=7).value, "근거")
            n_pat = sum(len(j["payload"]["wrong_patterns"]) for j, _ in bm.select_items(self.jobs, self.patterns, 3, 20261103))
            self.assertEqual(ws.max_row, 2 + n_pat)
            self.assertTrue(ws.cell(row=3, column=6).value.startswith("[문제 해석 오류]"))
            self.assertEqual(wb["비용"].cell(row=4, column=1).value, "gpt-6.1-sol")

    def test_retry_then_export(self):
        jobs = [j for j in self.jobs if len(j["payload"]["wrong_patterns"]) > 1][:3]
        client = FakeClient({j["item_id"]: j["payload"] for j in jobs}, bad_first=True)
        ae.time.sleep = lambda s: None
        records = {}
        for j in jobs:
            out = ae.analyze_item(client, self.cfg, j)
            self.assertEqual(out["status"], "ok")
            records[j["item_id"]] = {"item_id": j["item_id"], "model": "fake", "prompt_version": "t", **out}
        self.assertEqual(client.calls, len(jobs) + 1)  # 첫 응답만 검증 실패 후 재시도
        with tempfile.TemporaryDirectory() as d:
            stats = ae.export_tables(Path(d), self.packets, self.patterns, records)
            self.assertEqual(stats["pattern_rows"], sum(len(p) for p in self.patterns.values()))
            n_ok = sum(len(j["payload"]["wrong_patterns"]) for j in jobs)
            ok_attempts = sum(p["count"] for j in jobs for p in self.patterns[j["item_id"]] if p["pattern_id"])
            self.assertEqual(stats["attempts_by_status"]["ok"], ok_attempts)
            self.assertGreater(n_ok, 0)


if __name__ == "__main__":
    unittest.main()
