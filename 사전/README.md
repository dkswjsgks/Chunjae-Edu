# 사전 (지식 · KC · 오개념)

1단계에서 만들고 2단계 이후가 읽는 기준표다. Q행렬의 열은 이 사전의 ID만 쓴다. 토픽·문항·풀이는 `분석 데이터/`에 있다.

| 파일 | 한 행 | 규모 |
|---|---|---|
| `지식.csv` | 지식 하나 | 21개(1차 대상 5개·첫 실험 2개 표시) |
| `KC.csv` | KC 하나 | Eedi KC 54개 + 빈칸 KC 7개(`KC-N001~N007`) + 엑셀 밖 Eedi KC 2개(`KC-E297`, `KC-E415`). 묶은 버전 26묶음 |
| `오개념.csv` | KC–오개념 연결 하나 | 620행, 오개념 381개. 매핑 후보 556행(관련도 상·중) |
| `오류유형.csv` | 오개념 상위 분류 하나 | 5개 고정 |
| `원본/Eedi_KC_오개념_사전_1-1.xlsx` | 팀이 만든 원본 엑셀 | Eedi Misconceptions Graph v1.0 기반 |

연결: `지식.knowledge_id` ← `KC.knowledge_id`, `KC.kc_id` ← `오개념.kc_id`.

만드는 순서(레포 루트에서):
```powershell
python "1단계 사전/1_build_knowledge_dictionary.py"   # 지식.csv
python "1단계 사전/2_import_eedi_kc_dictionary.py"    # KC.csv, 오개념.csv (엑셀 변환 + 빈칸 KC)
python "1단계 사전/3_build_kc_groups.py"              # KC.csv의 kc_group 채움
```

규칙
- CSV를 손으로 고치지 않는다. 다시 만들 때 덮어써진다. 원본 엑셀이나 1단계 스크립트의 표(`GAP_KCS`, `GROUPS`)를 고친다.
- ID는 한 번 발급하면 바꾸지 않는다. Eedi 출처는 `KC-E<ConstructId>`, `MC-E<MisconceptionId>`, 새로 만든 것은 `KC-N<번호>`, `MC-N<번호>`, KC 묶음은 `KG-<번호>`.
- 아직 내용이 없는 열은 두지 않는다. 1단계 4(오개념 정비)가 정의·계산 경로·학생용 설명문 등을 채울 때 `오개념.csv`에 열을 추가한다.

## 지식.csv
| 열 | 뜻 |
|---|---|
| knowledge_id, knowledge_name | 지식 ID(분석 데이터와 같음), 이름 |
| semester_label | 예: 1학년 1학기 |
| n_topics, n_items, n_attempts, n_students, n_wrong | 토픽·문항·풀이·학생·원본 오답 수 |
| is_target, is_first_experiment | 1차 대상 5개, 첫 실험 2개면 1 |

## KC.csv
| 열 | 뜻 |
|---|---|
| kc_id | `KC-E<ConstructId>` 또는 `KC-N<번호>` |
| knowledge_id, knowledge_name | 이 KC가 속한 지식 |
| role | 핵심 / 보조 / 참고 (엑셀의 "구분") |
| kc_name_ko | KC 이름 |
| kc_group, kc_group_name | 묶은 버전의 KC(`KG-<번호>`)와 이름. 수의 개수·수의 종류·표기만 다른 KC를 묶는다(예: 음수가 하나/두 개/소수/세 개 이상 포함된 덧셈 → 음수가 포함된 덧셈). 묶이지 않은 KC는 혼자 한 묶음. `kc_size=group` 실행이 kc_id 대신 쓴다 |
| chunjae_topics | 엑셀의 대응 천재 토픽(수작업 초안, 토픽 이름을 줄여 적음) |
| construct_name_en, eedi_construct_id, eedi_subtopic | Eedi 원문 |
| source, status | eedi / new, active / draft |
| review_note | 빈칸 KC 초안의 근거 |

## 오개념.csv
| 열 | 뜻 |
|---|---|
| kc_id, misconception_id | 연결. 같은 오개념이 여러 KC에 걸치면 KC마다 한 행 |
| name_ko, name_en | 오개념 이름(LLM 초벌 번역, 검수 필요), 원문. 오개념마다 같다 |
| relevance | 이 KC에서의 관련도 상 / 중 / 하 (LLM 판정, 검수 필요) |
| use_in_mapping | 2단계 오개념 후보로 쓰면 1. 관련도 상·중은 1, 하는 0 |
| our_code_draft | 기존 12개 오류 코드 대응 초안 |
| eedi_pct | Eedi PercentageMisconceptionExistsInThisConstruct |
| source, status | eedi / 오답귀납, active |

`eedi_pct`는 오개념마다 합이 100인 값이다. "이 오개념이 어느 KC에서 나타나는지의 분포"이지 "이 KC에서 이 오개념이 흔한 정도"가 아니다. 선지별 오개념 순위에 쓰지 않는다.

## 오류유형.csv
| 열 | 뜻 |
|---|---|
| category_id, category_name | CAT-1~5: 개념 혼동, 절차·계산 오류, 선행지식 결손, 문제 조건 오독, 미응답·포기 |
| definition, advice_material, examples_1_1 | 정의, 조언 재료 종류, 1-1 예시 |

## 오개념 검수 현황 (2026-11-19)
첫 실험 지식 2개의 매핑 후보 오개념(use_in_mapping=1) 350개 중 349개를 검수해 `name_ko`(번역), `category_id`(상위 분류), `our_code`(기존 오류 코드와 같은 경우만), `reviewed_by`, `review_note`를 채웠다. 처음 53개는 팀 검토, 나머지 296개는 사용자가 위임해 Claude가 전수 확인했다(`reviewed_by` 열로 구분). 보류 1개: MC-E19483(지면층을 1층으로 생각함 — 한국에서는 성립하지 않아 팀 확인 필요). 제안된 관련도 변경은 KC마다 달라 사전에 반영하지 않았다. 설명문 열은 아직 사전에 반영하지 않았다(설명문 검토 시트는 `1단계 사전/4_오개념_정비/결과/1-4-설명문-20261119-01/`, 승인 전).
