import pandas as pd, numpy as np, json
D='/mnt/user-data/uploads/전처리 결과/'
a=pd.read_csv(D+'학습자 풀이 이력_전처리.csv',encoding='utf-8-sig',low_memory=False)
it=pd.read_csv(D+'문항 정보_전처리.csv',encoding='utf-8-sig')
on=pd.read_csv(D+'단원 및 지식_분류표.csv',encoding='utf-8-sig')
name=on.set_index('node_id').name
b=pd.read_csv(D+'빈칸별 응답_재채점.csv',encoding='utf-8-sig',low_memory=False)
# 분석 대상 풀이: 재풀이 제외, 판정보류 제외
A=a[(a.is_repeat_item==0)&(a.regraded_result!='ungraded')].copy()
print('attempts used',len(A),'of',len(a))
A['y']=(A.regraded_result=='correct').astype(int)
# 학생 능력(leave-one-out): 학생의 다른 문항 정답률
g=A.groupby('student_id').y; A['s_sum']=g.transform('sum'); A['s_n']=g.transform('size')
A['ability']=(A.s_sum-A.y)/(A.s_n-1)
A.loc[A.s_n<4,'ability']=np.nan   # 다른 문항 3개 미만이면 능력 추정 안 함
def disc(df):
    d=df.dropna(subset=['ability'])
    if len(d)<8 or d.y.nunique()<2 or d.ability.std()==0: return np.nan
    return np.corrcoef(d.y,d.ability)[0,1]
W=A[A.regraded_result.isin(['incorrect','partial'])&(A.response_state!='missing')]
def conc(s):
    if len(s)<3: return np.nan
    return s.value_counts().iloc[0]/len(s)
F=pd.DataFrame({
 'n':A.groupby('item_id').size(),
 'n_correct':A.groupby('item_id').y.sum(),
 'missing_rate':A.groupby('item_id').regraded_result.apply(lambda s:(s=='missing').mean()),
 'partial_rate':A.groupby('item_id').regraded_result.apply(lambda s:(s=='partial').mean()),
 'n_wrong_answered':W.groupby('item_id').size(),
 'wrong_concentration':W.groupby('item_id').response_normalized.apply(conc),
 'top_wrong_response':W.groupby('item_id').response_normalized.agg(lambda s:s.value_counts().index[0]),
 'discrimination':A.groupby('item_id').apply(disc,include_groups=False),
 'mean_ability':A.groupby('item_id').ability.mean(),
})
F['n_wrong_answered']=F.n_wrong_answered.fillna(0).astype(int)
F['p_correct']=(F.n_correct+1)/(F.n+2)
# 다단계 신호: 순서형 다빈칸 문항에서 부분정답 중 '첫 칸 정답 + 뒤 칸 오답' 비율
bb=b[(b.matching_mode=='ordered')]
pa=A[A.regraded_result=='partial'].attempt_id
bp=bb[bb.attempt_id.isin(pa)]
first=bp[bp.blank_index==1].set_index('attempt_id').grading_status
F['partial_first_ok_share']=bp.drop_duplicates('attempt_id').assign(f=lambda d:d.attempt_id.map(first)=='correct').groupby('item_id').f.mean()
meta=it.set_index('item_id')[['semester_label','knowledge_id','topic_id','item_form','difficulty_label','discrimination_label','question_text','diagram_reference','needs_content_review','answer_key_status']]
F=F.join(meta)
F['knowledge']=F.knowledge_id.map(name); F['topic']=F.topic_id.map(name)
ak=pd.read_csv(D+'문항별 빈칸_기준정답.csv',encoding='utf-8-sig').set_index('item_id')
F['expected_count']=ak.expected_count
F['q_len']=F.question_text.fillna('').str.len()
F.to_pickle('F.pkl')
print(F[['n','p_correct','missing_rate','partial_rate','wrong_concentration','discrimination']].describe().round(3))
for t in [(10,3),(10,5),(8,3),(15,3)]:
    m=(F.n>=t[0])&(F.n_wrong_answered>=t[1])&F.discrimination.notna()
    print(t,m.sum(), 'n>=',t[0],'but few wrong',((F.n>=t[0])&(F.n_wrong_answered<t[1])).sum())
