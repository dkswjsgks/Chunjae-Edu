# 사전 (지식 · KC · 오개념)

1단계에서 정비하고 2단계 이후가 읽어 쓰는 기준표다. Q행렬의 열은 이 사전의 ID만 쓴다.

출발점은 팀이 만든 `원본/Eedi_KC_오개념_사전_1-1.xlsx`(Eedi Misconceptions Graph v1.0, 첫 실험 지식 2개)다. `1단계 사전/2_import_eedi_kc_dictionary.py`가 이 엑셀을 아래 CSV로 변환한다.

| 파일 | 한 행 | 상태 |
|---|---|---|
| `지식_사전.csv` | 지식 하나 | 21개(1차 대상 5개·첫 실험 2개 표시) |
| `KC_사전.csv` | KC 하나 | Eedi KC 54개 + 빈칸 KC 초안 3개(`status=draft`) |
| `지식_KC_연결표.csv` | 지식–KC 연결 | 57행 |
| `오개념_사전.csv` | 오개념 하나 | 381개(엑셀 399행 중 18개는 두 지식에 걸쳐 한 행으로). 번역·관련도·코드 검수 필요 |
| `KC_오개념_연결표.csv` | KC–오개념 연결 | 620행. 매핑 후보 556행, 관련도 "하" 64행은 `use_in_mapping=0` |
| `오류유형_상위분류.csv` | 상위 분류 | 5개 고정 |

규칙
- ID는 한 번 발급하면 바꾸지 않는다. Eedi 출처는 `KC-E<ConstructId>`, `MC-E<MisconceptionId>`, 새로 만든 것은 `KC-N<번호>`, `MC-N<번호>`.
- 통합·폐기는 `status`와 `merged_into`로 표시하고 행을 지우지 않는다. 사람이 고친 행은 `reviewed_by`, `review_note`를 채운다.
- 이 폴더의 CSV를 손으로 고치면 다음 변환 때 덮어써진다. 원본 엑셀이나 1단계 스크립트에서 고친다.

## 열 정의

### 지식_사전.csv
| 열 | 뜻 |
|---|---|
| knowledge_id | 전처리 분류표의 node_id |
| knowledge_name | 지식 이름 |
| grade_semester | 학년-학기 |
| topic_ids / topic_names | 연결 토픽 (`;` 구분) |
| n_items / n_attempts / n_students / n_wrong | 기존 전처리 이력 기준 규모 |
| is_target / is_first_experiment | 1차 대상 5개 / 첫 실험 2개 |
| eedi_subtopic_candidates | 대응 Eedi SubTopic |

### KC_사전.csv
| 열 | 뜻 |
|---|---|
| kc_id | `KC-E<ConstructId>` 또는 새 KC `KC-N<번호>` |
| knowledge_name | 천재 지식단위 |
| role | 핵심 / 보조 / 참고 (엑셀의 "구분") |
| kc_name_ko | KC 한국어 이름 |
| construct_name_en | Eedi ConstructName 원문 |
| eedi_construct_id, eedi_subtopic | Eedi 출처 |
| chunjae_topics | 대응 천재 토픽(수작업 초안) |
| n_linked_misconceptions | 연결 오개념 수(엑셀 기준) |
| kc_group | KC 묶음 ID. 원래 크기로 쓸 때는 kc_id와 같고, 묶은 버전은 1단계 사전/3_KC_묶기 (--apply)가 채운다 |
| description | KC 정의(선택) |
| source | eedi / new |
| status | active / draft(초안, 검토 필요) / merged / dropped |
| merged_into, reviewed_by, review_note | 관리용 |

### 지식_KC_연결표.csv
| 열 | 뜻 |
|---|---|
| knowledge_id, knowledge_name, kc_id, role | 연결 |

### 오개념_사전.csv (코드북)
| 열 | 뜻 |
|---|---|
| misconception_id | `MC-E<MisconceptionId>` 또는 `MC-N<번호>` |
| name_ko, name_en | 한국어(LLM 초벌), 원문 |
| knowledge_names | 관련 천재 지식단위 (`;` 구분) |
| relevance | 상 / 중 / 하 (LLM 판정, 검수 필요). 지식단위별로 다르면 가장 높은 값 |
| our_code_draft | 기존 12개 코드 대응 초안 |
| category_id | 오류유형_상위분류.csv의 상위 분류 (1-3에서 채움) |
| n_linked_kc, max_pct, main_kc_name | 엑셀의 연결 KC 수, 최대 비중(%), 주 KC |
| definition, include_examples, exclude_examples | 정의, 포함 예(문항ID:선지), 배제 예 |
| typical_trace, trace_rule | 전형적 계산 경로, 코드 재계산 규칙 |
| student_explanation, teacher_note | 학생용 설명문(조언 뼈대), 교사용 메모 |
| source | eedi / 오답귀납 / 지도서 / 신규제안 |
| status, merged_into, reviewed_by, review_note | 관리용 |

### KC_오개념_연결표.csv
| 열 | 뜻 |
|---|---|
| kc_id, misconception_id | 연결 |
| knowledge_name | 천재 지식단위 |
| relevance | 상 / 중 / 하 |
| eedi_pct | Eedi PercentageMisconceptionExistsInThisConstruct |
| use_in_mapping | 2단계 오개념 후보로 쓰면 1. 기본값: 관련도 상·중은 1, 하는 0 |
| link_source | eedi / 오답귀납 / 수작업 |

### Eedi 비중(%) 주의
`eedi_pct`는 오개념마다 합이 100인 값이다. "이 오개념이 어느 KC(construct)에서 나타나는지의 분포"이지 "이 KC에서 이 오개념이 흔한 정도"가 아니다. 선지별 오개념 순위에 쓰지 않는다.
