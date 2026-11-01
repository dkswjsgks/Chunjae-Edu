"""표기·빈칸 의미를 보존하는지와 실제 산출물의 연결 관계를 검사한다."""
import csv
import json
import os
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from preprocess import ROOT, OUTPUT_FILES, normalize, tokens, grade_response, sha256, add_history_features


def read(name):
    with (ROOT / '전처리 결과' / OUTPUT_FILES[name]).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


class NormalizationTests(unittest.TestCase):
    def test_numeric_notation(self):
        for value in [' ＋３.０ ', '+3', '(+3)', '3.00']:
            self.assertEqual(normalize(value), '3')
        self.assertEqual(normalize('− 14'), '-14')
        self.assertEqual(normalize('-0.0'), '0')
        self.assertEqual(normalize('0.014'), '0.014')

    def test_math_symbols_keep_meaning(self):
        self.assertEqual(normalize('＜'), '<')
        self.assertEqual(normalize('≦'), '≤')
        self.assertNotEqual(normalize('<'), normalize('≤'))
        self.assertEqual(normalize('①'), '①')
        self.assertEqual(normalize('㉠'), '㉠')
        self.assertEqual(normalize('2²'), '2²')
        self.assertNotEqual(normalize('1/2'), normalize('12'))

    def test_scoped_aliases(self):
        self.assertEqual(normalize('덧셈의 교환 법칙'), '교환법칙')
        self.assertEqual(normalize('덧셈의역원'), '덧셈의역원')
        self.assertEqual(normalize('십각형'), normalize('10각형'))
        self.assertEqual(normalize('첫', {'첫': '1'}), '1')
        self.assertEqual(normalize('첫'), '첫')

    def test_geometry_does_not_corrupt_congruence_rules(self):
        self.assertEqual(normalize('DA', geometry=True), normalize('AD', geometry=True))
        self.assertEqual(normalize('BAC', geometry=True), normalize('CAB', geometry=True))
        self.assertNotEqual(normalize('ABC', geometry=True), normalize('BAC', geometry=True))
        self.assertEqual(normalize('RHA', geometry=True), 'rha')
        self.assertEqual(normalize('ABC'), 'abc')

    def test_missing_tokens_preserve_positions(self):
        self.assertEqual(tokens('/^ROW^//^ROW^/'), [None, None, None])
        self.assertEqual(tokens('1/^ROW^//^ROW^/모름'), ['1', None, None])
        self.assertEqual(normalize('모름'), None)
        self.assertEqual(normalize('?'), '?')


class GradingTests(unittest.TestCase):
    def test_ordered_partial(self):
        result, states, reference = grade_response(['9', '3', '-2'], [['9', '2', '-2']], 'ordered')
        self.assertEqual(result, 'partial')
        self.assertEqual(states, ['correct', 'incorrect', 'correct'])

    def test_unordered_and_multiplicity(self):
        self.assertEqual(grade_response(['b', 'a'], [['a', 'b']], 'unordered')[0], 'correct')
        self.assertEqual(grade_response(['a', 'a'], [['a', 'b']], 'unordered')[1], ['correct', 'incorrect'])

    def test_multiple_vectors_cannot_be_mixed(self):
        vectors = [['8', '5', '8'], ['5', '8', '8']]
        self.assertEqual(grade_response(['8', '8', '8'], vectors, 'ordered')[0], 'partial')

    def test_multiselect_missing_option(self):
        self.assertEqual(grade_response(['①'], [['①', '⑤']], 'multi_select')[0], 'partial')
        self.assertEqual(grade_response(['⑤', '①'], [['①', '⑤']], 'multi_select')[0], 'correct')

    def test_missing_and_unknown_keys(self):
        self.assertEqual(grade_response([None, None], [['1', '2']], 'ordered')[0], 'missing')
        self.assertEqual(grade_response(['1'], [], 'ordered')[0], 'ungraded')
        self.assertEqual(grade_response(['1'], [['1']], 'ordered', usable=False)[0], 'ungraded')


class HistoryTests(unittest.TestCase):
    def test_history_uses_only_strictly_earlier_times(self):
        def attempt(item, time):
            return dict(student_id='student', item_id=item, knowledge_id='knowledge', test_completed_at=time)
        first = attempt('item1', '2026-01-01 12:00:00')
        same_test = attempt('item2', '2026-01-01 12:00:00')
        repeat1 = attempt('item1', '2026-01-02 12:00:00')
        repeat2 = attempt('item1', '2026-01-02 12:00:00')
        later = attempt('item3', '2026-01-03 12:00:00')
        rows = [later, repeat2, same_test, first, repeat1]
        add_history_features(rows)
        self.assertEqual(first['prior_knowledge_attempt_count'], 0)
        self.assertEqual(same_test['prior_knowledge_attempt_count'], 0)
        self.assertEqual(repeat1['prior_item_attempt_count'], 1)
        self.assertEqual(repeat2['prior_item_attempt_count'], 1)
        self.assertEqual(repeat1['same_time_item_attempt_count'], 2)
        self.assertEqual(later['prior_knowledge_attempt_count'], 4)
        self.assertEqual(later['prior_knowledge_distinct_item_count'], 2)
        self.assertEqual(first['is_first_observed_item'], 1)
        self.assertEqual(repeat1['is_repeat_item'], 1)

    def test_simultaneous_first_observations_have_no_invented_order(self):
        rows = [dict(student_id='s', item_id='i', knowledge_id='k', test_completed_at='2026-01-01 12:00:00')
                for _ in range(2)]
        add_history_features(rows)
        self.assertTrue(all(row['prior_item_attempt_count'] == 0 for row in rows))
        self.assertTrue(all(row['is_first_observed_item'] == 0 for row in rows))


class ActualOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.attempts = read('attempts.csv')
        cls.items = {r['item_id']: r for r in read('items.csv')}
        cls.keys = {r['item_id']: r for r in read('answer_keys.csv')}
        cls.blanks = read('blank_responses.csv')
        cls.nodes = {r['node_id']: r for r in read('ontology_nodes.csv')}

    def test_originals_and_row_counts_preserved(self):
        summary = json.loads((ROOT / '전처리 결과' / OUTPUT_FILES['audit_summary.json']).read_text(encoding='utf-8'))
        self.assertEqual(len(self.attempts), 23409)
        self.assertEqual(len(self.items), 2197)
        self.assertEqual(sum(int(r['columns_repaired']) for r in self.attempts), 1908)
        self.assertEqual(sum(bool(r['image_path']) for r in self.items.values()), 521)

    def test_original_hashes_when_raw_data_is_available(self):
        raw_root = Path(os.environ.get('CHUNJAE_RAW_ROOT', str(ROOT / '원본 데이터')))
        summary = json.loads((ROOT / '전처리 결과' / OUTPUT_FILES['audit_summary.json']).read_text(encoding='utf-8'))
        if not all((raw_root / name).is_file() for name in summary['input_sha256']):
            self.skipTest('원본은 별도 제공. CHUNJAE_RAW_ROOT를 지정하면 원본 해시도 검증함')
        for name, digest in summary['input_sha256'].items():
            self.assertEqual(sha256(raw_root / name), digest)

    def test_ontology_is_connected_and_acyclic(self):
        self.assertEqual(sum(n['node_type'] == 'knowledge' for n in self.nodes.values()), 21)
        for node in self.nodes.values():
            visited = set()
            while node['parent_id']:
                self.assertNotIn(node['node_id'], visited)
                visited.add(node['node_id'])
                self.assertIn(node['parent_id'], self.nodes)
                node = self.nodes[node['parent_id']]
        for attempt in self.attempts:
            self.assertIn(attempt['item_id'], self.items)
            for key in ['grade_id', 'semester_id', 'major_id', 'middle_id', 'minor_id', 'topic_id', 'knowledge_id']:
                self.assertIn(attempt[key], self.nodes)
        links = read('topic_knowledge.csv')
        for link in links:
            self.assertEqual(self.nodes[link['topic_id']]['node_type'], 'topic')
            self.assertEqual(self.nodes[link['knowledge_id']]['node_type'], 'knowledge')

    def test_blank_records_reconstruct_each_input(self):
        groups = defaultdict(list)
        for row in self.blanks:
            groups[row['attempt_id']].append(row)
        for attempt in self.attempts:
            observed = [b for b in groups[attempt['attempt_id']] if b['token_origin'] == 'observed']
            self.assertEqual('/^ROW^/'.join(b['response_token_raw'] for b in observed), attempt['response_raw'])
            self.assertEqual(len(groups[attempt['attempt_id']]), max(int(attempt['response_token_count']), int(attempt['expected_token_count'] or 0)))

    def test_source_missing_and_known_y_errors(self):
        missing = [a for a in self.attempts if not a['source_correctness']]
        self.assertEqual(len(missing), 8)
        self.assertTrue(all(a['response_state'] == 'missing' for a in missing))
        wrong_y = [a for a in self.attempts if a['item_id'] == '41020553' and a['response_raw'] == '63/^ROW^/4']
        self.assertEqual(len(wrong_y), 1)
        self.assertEqual(wrong_y[0]['source_correctness'], 'Y')
        self.assertEqual(wrong_y[0]['regraded_result'], 'partial')

    def test_manual_keys_and_fixed_negative_sign(self):
        self.assertEqual(len(read('manual_59_review.csv')), 59)
        self.assertEqual(json.loads(self.keys['40770455']['expected_vectors']), [['4', '3']])
        self.assertEqual(json.loads(self.keys['41020690']['expected_vectors']), [['4', '11', '17', '111', '211', '330', '64', '15']])
        self.assertEqual(json.loads(self.keys['40770383']['expected_vectors']), [['a', 'c', 'b']])
        for item_id in ['40769436', '41022504', '41022185', '41022201']:
            self.assertEqual(self.keys[item_id]['usable_for_regrading'], '0')
            self.assertTrue(all(a['regraded_result'] in {'missing', 'ungraded'} for a in self.attempts if a['item_id'] == item_id))

    def test_packets_have_no_student_ids_and_match_counts(self):
        with (ROOT / '전처리 결과' / OUTPUT_FILES['item_packets.jsonl']).open(encoding='utf-8') as handle:
            packets = [json.loads(line) for line in handle]
        self.assertEqual(len(packets), len(self.items))
        self.assertEqual(sum(sum(p['historical_outcomes']['source_correctness_counts'].values()) for p in packets), len(self.attempts))
        self.assertEqual(sum(sum(r['count'] for r in p['historical_outcomes']['wrong_response_distribution']) for p in packets), 9356)
        self.assertTrue(all('student_id' not in json.dumps(p) for p in packets))

    def test_all_output_files_have_korean_names(self):
        folder = ROOT / '전처리 결과'
        for old_name, name in OUTPUT_FILES.items():
            self.assertTrue((folder / name).is_file(), name)
            self.assertTrue(any('가' <= c <= '힣' for c in name), name)
            self.assertFalse((folder / old_name).exists(), old_name)

    def test_repeat_features_against_original_timestamps(self):
        groups = defaultdict(list)
        for attempt in self.attempts:
            groups[(attempt['student_id'], attempt['item_id'])].append(attempt)
        for group in groups.values():
            for attempt in group:
                prior = sum(other['test_completed_at'] < attempt['test_completed_at'] for other in group)
                simultaneous = sum(other['test_completed_at'] == attempt['test_completed_at'] for other in group)
                self.assertEqual(int(attempt['prior_item_attempt_count']), prior)
                self.assertEqual(int(attempt['same_time_item_attempt_count']), simultaneous)
                self.assertEqual(int(attempt['is_repeat_item']), int(prior > 0))

    def test_student_summary_keeps_denominators_and_missing_distinct(self):
        summaries = read('student_knowledge_summary.csv')
        self.assertEqual(sum(int(s['총풀이수']) for s in summaries), len(self.attempts))
        self.assertEqual(sum(int(s['원본채점_누락수']) for s in summaries), 8)
        self.assertEqual(sum(int(s['전체_미응답수']) for s in summaries), 1828)
        self.assertEqual(sum(int(s['채점_불일치수']) for s in summaries), 38)
        self.assertEqual(sum(int(s['재풀이수']) for s in summaries), sum(int(a['is_repeat_item']) for a in self.attempts))
        for summary in summaries:
            denominator = int(summary['원본채점_있는수'])
            self.assertEqual(summary['집계범위'], '제공된 전체 이력')
            if denominator:
                self.assertAlmostEqual(float(summary['원본_정답률']), int(summary['원본_정답수']) / denominator, places=6)
            else:
                self.assertEqual(summary['원본_정답률'], '')
            difficulties = json.loads(summary['난이도별_관측통계'])
            self.assertEqual(sum(d['관측수'] for d in difficulties.values()), int(summary['총풀이수']))
            self.assertEqual(sum(d['원본정답수'] for d in difficulties.values()), int(summary['원본_정답수']))

    def test_review_reasons_are_linked_to_each_attempt(self):
        for attempt in self.attempts:
            reasons = json.loads(attempt['analysis_cautions'])
            self.assertEqual('원본채점과_재채점_불일치' in reasons, attempt['grading_disagreement'] == '1')
            self.assertEqual('빈칸_기준정답_추가검토' in reasons, attempt['answer_key_needs_review'] == '1')
            self.assertEqual('동일문항_재풀이' in reasons, attempt['is_repeat_item'] == '1')

    def test_damaged_explanations_are_marked_for_content_review(self):
        for item in self.items.values():
            if item['explanation_double_questionmark'] == '1':
                self.assertEqual(item['needs_content_review'], '1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
