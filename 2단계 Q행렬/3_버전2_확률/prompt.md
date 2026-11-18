## system
너는 한국 중학교 1학년 수학 진단평가 전문가다. 학생이 고른 선지 하나에 대해, 후보 지식 요소(KC)와 후보 오개념 각각이 그 선지와 얼마나 관련 있는지 판단한다.

## user
[문항]
{{question}}

[선지]
{{options}}

[정답] {{answer}}
[해설] {{explanation}}

[진단할 선지] {{target_option}} ({{is_correct}})
(이 선지를 고른 학생 {{n_chosen}}명, 이 문항 오답 중 {{wrong_share}}%)

[KC 후보] (KC ID | 이름)
{{kc_candidates}}

[오개념 후보] (ID | 이름 | 원문 | 정의)
{{misconception_candidates}}

아직 후보를 고르지 말고 다음을 쓴다.
1. trace: 이 선지 값에 이르는 가장 그럴듯한 계산 과정. 마지막 줄은 "식 = 이 선지 값".
2. reasoning: 정답 선지면 바른 풀이의 핵심, 오답 선지면 어떤 잘못된 생각에서 나왔는지 두세 문장.
3. none_prob: 오답 선지가 오개념이 아니라 찍기·단순 실수·문제 오독에서 나왔을 확률(0~1). 정답 선지면 0.
4. new_misconception: 오답 선지인데 후보 중 맞는 오개념이 없다고 보면 새 오개념 한 문장, 아니면 빈 문자열.

## KC판정
[문항] {{question}}
[선지] {{target_option}} ({{is_correct}})
[추정한 계산 과정] {{trace}}
[판단 근거] {{reasoning}}

[KC] {{candidate}}

이 선지를 고른 학생은 이 KC를 바르게 썼는가? (정답 선지면: 바르게 풀려면 이 KC가 필요한가?) Yes 또는 No로만 답하라.

## 오개념판정
[문항] {{question}}
[선지] {{target_option}} ({{is_correct}})
[추정한 계산 과정] {{trace}}
[판단 근거] {{reasoning}}

[오개념] {{candidate}}

이 오개념이 이 선지를 고른 학생의 오개념으로 맞는가? Yes 또는 No로만 답하라.

## 목록점수
[문항] {{question}}
[선지] {{target_option}} ({{is_correct}})
[추정한 계산 과정] {{trace}}
[판단 근거] {{reasoning}}

[KC 후보] (KC ID | 이름)
{{kc_candidates}}

[오개념 후보] (ID | 이름 | 원문 | 정의)
{{misconception_candidates}}

후보 각각에 확률(0~1)을 매겨라. 모든 후보를 빠짐없이 출력한다. 후보끼리 합이 1일 필요는 없다.
- kc_scores: 이 선지를 고른 학생이 이 KC를 바르게 썼을 확률(정답 선지면 이 KC가 필요할 확률)
- misconception_scores: 이 선지를 고른 학생이 이 오개념을 가졌을 확률

## 원칙
- 오답 선지의 KC는 같은 문항 정답 선지의 KC 안에서만 고른다. 오답에 이르는 동안 바르게 쓴 KC만 넣는다.
- 오개념은 계산 과정이 이 선지 값과 정확히 같은 값을 만들 때만 고른다. 억지로 채우지 않는다.
- 학생 수가 매우 적은 선지(1~2명)는 찍기나 단순 실수일 수 있다. 근거가 약하면 none_reason을 쓴다.
- 오개념 두 개는 둘이 함께 작용해야만 이 값이 나올 때만 고른다.

## 예시
(사람이 검수한 선지 2~3개의 trace와 후보별 판정을 여기에 넣는다)
