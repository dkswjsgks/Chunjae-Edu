import pandas as pd, numpy as np, re
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold
X=pd.read_pickle('X_eb.pkl')
it=pd.read_csv('/mnt/user-data/uploads/전처리 결과/문항 정보_전처리.csv',encoding='utf-8-sig').set_index('item_id')
q=it.question_text.fillna(''); ex=it.explanation_text.fillna('')
C=pd.DataFrame(index=it.index)
C['q_len']=np.log1p(q.str.len()); C['ex_len']=np.log1p(ex.str.len())
C['frac']=q.str.count(r'\\frac'); C['abs']=q.str.count(r'\|')/2; C['dot']=q.str.contains(r'\\dot').astype(int)
C['all_choose']=q.str.contains('모두').astype(int); C['not_correct']=q.str.contains('않은|아닌').astype(int)
C['img']=it.question_image_description.notna().astype(int); C['nums']=q.str.count(r'\d+')
C['cond']=q.str.count(r'\(가\)|\(나\)|㉠|㉡|\[조건\]')
C['ex_lines']=ex.str.count('\n')
K=pd.get_dummies(X.knowledge_id,prefix='k').astype(int)
Z=C.join(K).loc[X.index].fillna(0)
def cvr2(target,base,weight,mask):
    y=(target-base)[mask].values; w=weight[mask].values; Zm=Z[mask].values
    pred=np.zeros_like(y)
    for tr,te in KFold(5,shuffle=True,random_state=0).split(Zm):
        m=RidgeCV(alphas=np.logspace(-2,3,20)).fit(Zm[tr],y[tr],sample_weight=w[tr]); pred[te]=m.predict(Zm[te])
    return 1-np.sum(w*(y-pred)**2)/np.sum(w*(y-np.average(y,weights=w))**2)
m=X.n>=10
print('n items',m.sum())
print('정답률: 집단평균 대비 잔차를 내용특징이 설명하는 비율(CV R2)',round(cvr2(X.k_correct/X.n.clip(lower=1),X.p_prior,X.n,m),3))
print('정답률: 집단없이(전체평균) 내용특징 R2',round(cvr2(X.k_correct/X.n.clip(lower=1),pd.Series(X.k_correct.sum()/X.n.sum(),X.index),X.n,m),3))
print('미응답',round(cvr2(X.k_missing/X.n.clip(lower=1),X.miss_prior,X.n,m),3))
mm=m&X.multi
print('일부정답(다빈칸)',round(cvr2(X.k_partial/X.n.clip(lower=1),X.part_prior,X.n,mm),3))
mc=(X.n_wrong_answered>=5)
print('최빈오답',round(cvr2(X.k_top_wrong/X.n_wrong_answered.clip(lower=1),X.conc_prior,X.n_wrong_answered,mc),3))
Z.to_pickle('Z_content.pkl')
