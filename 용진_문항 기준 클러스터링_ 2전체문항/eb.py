import pandas as pd, numpy as np
D='/mnt/user-data/uploads/전처리 결과/'
a=pd.read_csv(D+'학습자 풀이 이력_전처리.csv',encoding='utf-8-sig',low_memory=False)
it=pd.read_csv(D+'문항 정보_전처리.csv',encoding='utf-8-sig')
on=pd.read_csv(D+'단원 및 지식_분류표.csv',encoding='utf-8-sig'); nm=on.set_index('node_id').name
ak=pd.read_csv(D+'문항별 빈칸_기준정답.csv',encoding='utf-8-sig').set_index('item_id')
A=a[(a.is_repeat_item==0)&(a.regraded_result!='ungraded')].copy()
A['y']=(A.regraded_result=='correct').astype(int)
# --- 메타데이터 (모든 문항에 존재) ---
M=it.set_index('item_id')[['semester_label','knowledge_id','topic_id','item_form','difficulty_label','discrimination_label','question_text','needs_content_review']].copy()
M['expected_count']=ak.expected_count
# 풀이 이력이 없는 문항은 응답 토큰 수를 알 수 없음 -> 정답 텍스트로 대체 추정하지 않고 1로 둠(표시)
M['expected_count_unknown']=M.expected_count.isna().astype(int)
M['expected_count']=M.expected_count.fillna(1)
M['multi']=(M.expected_count>1)
M['mc']=M.item_form.isin(['5지 선택','자유 선지형'])
M['diff']=M.difficulty_label.fillna('unknown').replace({'very easy':'easy','very hard':'hard'})
M['g_pm']=M['diff']+'|'+np.where(M.mc,'MC','SA')+'|'+np.where(M.multi,'multi','single')   # 정답률·미응답 사전집단
M['g_c']=np.where(M.mc,'MC','SA')+'|'+np.where(M.multi,'multi','single')                  # 오답쏠림·일부정답 사전집단
# --- 학생 실력 축소추정 (베타-이항) ---
st=A.groupby('student_id').y.agg(['sum','size'])
def mom_strength(k,n):
    p=k/n; mu=k.sum()/n.sum(); vb=np.var(p)-np.mean(p*(1-p)/n)
    vb=max(vb,1e-4); return mu, max(mu*(1-mu)/vb-1,1.0)
mu_s,m_s=mom_strength(st['sum'][st['size']>=5],st['size'][st['size']>=5])
A=A.join(st,on='student_id')
A['ability']=((A['sum']-A.y)+m_s*mu_s)/((A['size']-1)+m_s)   # 자기 문항 제외 + 축소
print(f'student prior mu={mu_s:.3f} strength={m_s:.1f}')
# --- 문항별 원시 집계 ---
g=A.groupby('item_id')
R=pd.DataFrame({'n':g.size(),'k_correct':g.y.sum(),
 'k_missing':g.regraded_result.apply(lambda s:(s=='missing').sum()),
 'k_partial':g.regraded_result.apply(lambda s:(s=='partial').sum())})
W=A[A.regraded_result.isin(['incorrect','partial'])&(A.response_state!='missing')]
wc=W.groupby('item_id').response_normalized.agg(lambda s:s.value_counts().iloc[0]); wn=W.groupby('item_id').size()
R['n_wrong_answered']=wn; R['k_top_wrong']=wc
R['top_wrong_response']=W.groupby('item_id').response_normalized.agg(lambda s:s.value_counts().index[0])
def corr(d):
    if len(d)<4 or d.y.nunique()<2 or d.ability.std()==0: return np.nan
    return np.corrcoef(d.y,d.ability)[0,1]
R['r_raw']=g.apply(corr,include_groups=False); R['n_pairs']=g.size()
X=M.join(R); X[['n','k_correct','k_missing','k_partial','n_wrong_answered','k_top_wrong','n_pairs']]=X[['n','k_correct','k_missing','k_partial','n_wrong_answered','k_top_wrong','n_pairs']].fillna(0)
# --- 베타-이항 경험적 베이즈: 집단 평균(사전 평균) + 공통 사전 강도 ---
def eb(k,n,grp,minn=10,name=''):
    ok=n>=minn
    mu_g=(k[ok].groupby(grp[ok]).sum()+0.5)/(n[ok].groupby(grp[ok]).sum()+1)
    glob=(k[ok].sum()+0.5)/(n[ok].sum()+1)
    mu=grp.map(mu_g).fillna(glob)
    p=(k[ok]/n[ok]); vb=np.var(p-mu[ok])-np.mean(p*(1-p)/n[ok]); vb=max(vb,1e-4)
    mm=float(np.mean(mu[ok]*(1-mu[ok])))
    m=max(mm/vb-1,1.0)
    print(f'{name}: prior strength m={m:.1f} (풀이 {m:.0f}건만큼의 사전정보)')
    post=(k+m*mu)/(n+m)
    return post, mu, m
X['p_post'],X['p_prior'],m_p=eb(X.k_correct,X.n,X.g_pm,name='정답률')
X['miss_post'],X['miss_prior'],m_m=eb(X.k_missing,X.n,X.g_pm,name='미응답률')
X['part_post'],X['part_prior'],m_pa=eb(X.k_partial,X.n,X.g_c,name='일부정답률')
X['conc_post'],X['conc_prior'],m_c=eb(X.k_top_wrong,X.n_wrong_answered,X.g_c,minn=5,name='최빈오답비중')
# --- 변별도: Fisher z 정밀도 가중 축소 ---
z=np.arctanh(X.r_raw.clip(-0.99,0.99)); w=(X.n_pairs-3).clip(lower=0)
okz=z.notna()&(X.n_pairs>=10)
z0=z[okz].groupby(X.g_pm[okz]).mean(); zg=z[okz].mean()
X['z_prior']=X.g_pm.map(z0).fillna(zg)
tau2=max(np.var(z[okz]-X.z_prior[okz])-np.mean(1/w[okz]),1e-3); w0=1/tau2
print(f'변별도: 사전 강도 w0={w0:.1f} (상관계수 표본 {w0+3:.0f}쌍 상당)')
zz=z.fillna(0); ww=np.where(z.notna(),w,0)
X['z_post']=(ww*zz+w0*X.z_prior)/(ww+w0); X['z_post_var']=1/(ww+w0)
X['disc_post']=np.tanh(X.z_post)
X['reliability_p']=X.n/(X.n+m_p)   # 데이터가 사후값에 기여한 비중
X['knowledge']=X.knowledge_id.map(nm); X['topic']=X.topic_id.map(nm)
X.attrs.update(m_p=m_p,m_m=m_m,m_pa=m_pa,m_c=m_c,w0=w0)
X.to_pickle('X_eb.pkl')
print(len(X),'items; no attempts:',(X.n==0).sum())
print(X[['p_post','miss_post','part_post','conc_post','disc_post','reliability_p']].describe().round(3))
print(pd.cut(X.n,[-1,0,2,4,9,19,1000]).value_counts().sort_index())
