# 분석 데이터

파이프라인(1~6단계)이 읽는 학생·문항 데이터다. `0단계 데이터/1_build_analysis_tables.py`가 `데이터 전처리/전처리 결과/`를 조인·정리해 만든다. 손으로 고치지 않는다. 전처리 결과가 바뀌면 다시 실행한다.

```powershell
python "0단계 데이터/1_build_analysis_tables.py"
```

코드에서는 `공통/data_io.py`의 `load_topics()`, `load_items()`, `load_attempts()`, `load_blank_responses()`로 읽는다. ID 열은 모두 문자열이다.

| 파일 | 한 행 | 규모 | 연결 |
|---|---|---|---|
| `토픽.csv` | 토픽 하나 | 66 | `knowledge_id` → 사전/지식.csv |
| `문항.csv` | 문항 하나 | 2,197 | `topic_id` → 토픽.csv |
| `풀이.csv` | 학생이 문항 하나에 낸 응답 하나 | 23,409 | `item_id` → 문항.csv |
| `빈칸응답.csv` | 응답의 입력칸(또는 복수선택 토큰) 하나 | 32,546 | `attempt_id` → 풀이.csv |

문항별 LLM 입력자료(`문항별 인공지능 분석_입력자료.jsonl`)는 전처리 결과 폴더의 것을 그대로 쓴다(`data_io.load_item_packets()`).

## 토픽.csv
| 열 | 뜻 |
|---|---|
| topic_id, topic_name | 토픽 ID와 원본 `토픽` 열 값 |
| knowledge_id, knowledge_name | 토픽이 속한 지식(토픽 하나는 지식 하나에 속한다) |
| major_name, middle_name, minor_name | 대단원, 중단원, 소단원 |
| semester_label | 예: 1학년 1학기 |

## 문항.csv
| 열 | 뜻 |
|---|---|
| item_id | 문항 ID |
| semester_label, major_name, middle_name, minor_name, topic_id, topic_name, knowledge_id, knowledge_name | 분류. 이력이 없는 5문항은 비어 있다 |
| item_form | 5지 선택 / 단답 유순형 / 단답 무순형 / 자유 선지형 |
| difficulty_label, discrimination_label | 원본 난이도, 변별도 |
| question_text, question_image_description | 문제(손상 복원본), 문제 이미지 설명 |
| option_1 ~ option_5 | 객관식 선지(단답형은 비어 있음) |
| explanation_text, explanation_image_description | 해설, 해설 이미지 설명 |
| image_path, image_contains_answer_or_solution | 문제 PNG 경로. PNG에 정답·해설이 함께 있을 수 있어 1이면 학생에게 그대로 보여주지 않는다 |
| answer_raw | 원본 정답 표기 |
| answer_mode | ordered(순서대로) / unordered(단답 무순형) / multi_select(복수선택) |
| answer_expected_count, answer_expected_vectors | 입력칸 수, 허용 정답 벡터(JSON) |
| answer_key_source, answer_key_status | 정답키 출처와 확정 수준. `blocked_source_defect`, `unresolved`는 정답 미확정이라 Q행렬에서 제외 |
| answer_usable_for_regrading, answer_key_needs_review, answer_key_note | 재채점 사용 가능 여부, 추가 검토 필요(정답자 1명뿐 등), 수작업 메모 |
| needs_content_review | 그림 누락 후보, `??` 손상, 해설 부족 등 내용 검토가 필요하면 1 |
| quality_flags | 품질 표시 목록(JSON): explanation_text_missing, diagram_context_missing_candidate, question/explanation_double_questionmark, content_manual_review, no_attempt_metadata |

## 풀이.csv
| 열 | 뜻 |
|---|---|
| attempt_id, student_id, test_id | 응답, 학생, 시험지 ID |
| test_completed_at | 시험 완료일시. 문항별 풀이 시각이 아니다. 같은 시각 응답의 선후는 알 수 없다 |
| item_order | 시험지 안 문항 순서 |
| item_id, knowledge_id, topic_id | 문항과 분류(문항.csv와 같다) |
| response_raw, response_normalized | 원본 응답, 비교용 정규화 응답(JSON 배열, 빈 응답은 null) |
| response_state | answered / partial_missing(일부 칸 빈칸) / missing(전체 미응답·"모름") |
| response_layout_mismatch | 응답 칸 수가 정답 칸 수와 다르면 1 |
| source_correctness | 기업 원본 정오답 Y/N(빈값 8건). 공식 채점 |
| regraded_result, regraded_correctness | 전처리 재채점: correct / partial / incorrect / missing / ungraded, 문항 단위 Y/N. 원본과 비교할 때 보조로 쓴다 |
| grading_disagreement | 원본과 재채점의 Y/N이 다르면 1(38건) |
| prior_item_attempt_count, is_repeat_item | 같은 학생이 같은 문항을 이전 시각에 푼 횟수, 1 이상이면 1 |
| is_first_observed_item | 이 자료 안에서 그 학생·문항의 첫 기록이면 1 |
| prior_knowledge_attempt_count, prior_knowledge_distinct_item_count | 같은 학생·지식의 이전 응답 수, 그중 서로 다른 문항 수 |
| analysis_cautions | 해석 주의 목록(JSON): 문항내용_검토필요, 전체_미응답, 동일문항_재풀이, 빈칸_기준정답_추가검토 등 |

## 빈칸응답.csv
| 열 | 뜻 |
|---|---|
| attempt_id, item_id, blank_index | 응답, 문항, 입력 위치(복수선택은 선택 토큰 순서) |
| response_token_raw, response_token_normalized | 그 칸의 원본 값, 정규화 값 |
| expected_token, reference_vector | 순서형 문항에서 비교한 정답값, 비교에 쓴 정답 벡터 |
| matching_mode | ordered / unordered / multi_select |
| token_origin | observed(원본에 있던 칸) / padded_missing(칸이 모자라 채운 빈칸) |
| positional_alignment_verified | 칸 수가 맞고 순서형 비교를 적용했으면 1 |
| grading_status | 칸별 correct / incorrect / missing / ungraded |

## 이 폴더에 없는 열과 파일

검토·추적용이라 파이프라인에서 쓰지 않는다. 필요하면 `데이터 전처리/전처리 결과/`에서 읽는다(설명은 그 폴더의 `전처리 결과_설명서.md`).

| 원래 위치 | 빠진 것 | 이유 |
|---|---|---|
| 문항 정보_전처리.csv | grade_id ~ minor_id | 이름 열(major_name 등)과 topic_id·knowledge_id로 대체 |
| | question_text_raw, explanation_text_raw | 복원 전 원문. 정리본과 99.95% 같고 차이는 복원 이력에 있다 |
| | image_sha256 | 파일 무결성 확인용 |
| | explanation_text_missing, diagram_context_missing_candidate, question_double_questionmark, explanation_double_questionmark | quality_flags에 같은 내용이 있다 |
| | explanation_context_available, diagram_reference | 해설 텍스트·이미지 설명 유무, "그림·수직선" 단어 포함 여부. 해당 열에서 다시 계산할 수 있다 |
| 문항별 빈칸_기준정답.csv | observed_correct_count, observed_correct_variant_count, response_token_counts, geometry_name_equivalence | 정답키를 만들 때 쓴 근거 통계 |
| 학습자 풀이 이력_전처리.csv | source_record_number, columns_repaired | 원본 행 추적, 컬럼 밀림 복원 표시 |
| | grade_id ~ minor_id | 문항.csv에서 찾는다 |
| | test_score_raw | 같은 시험의 정답 결과가 들어 있어 예측 평가에 쓰면 정답 정보가 샌다 |
| | response_token_count, expected_token_count | 빈칸응답.csv에서 센다 |
| | answer_key_source, answer_key_status, answer_key_needs_review, item_needs_content_review | 문항 단위 값이라 문항.csv에 있다(값 100% 일치 확인) |
| | same_time_item_attempt_count | 모든 행이 1 |
| 빈칸별 응답_재채점.csv | key_status | 문항.csv의 answer_key_status와 같다 |
| 파일 전체 | 데이터_검토 필요 목록, 데이터_복원 및 수정 이력, 원본 채점과 재채점_불일치, 응답값_정규화 이력, 정답 응답_관측 목록, 정답자 없는 59문항_검토, 전처리 파일_이름 안내, 전처리_검증 요약.json | 전처리 검토·추적 기록 |
| | 학생별 지식_학습 요약 | 전 기간 집계라 과거 시점 평가에 쓰면 미래 정보가 섞인다. 4단계는 시점별로 다시 집계한다 |
| | 단원 및 지식_분류표, 토픽과 지식_연결표 | 토픽.csv와 문항.csv의 이름 열로 조인했다 |
