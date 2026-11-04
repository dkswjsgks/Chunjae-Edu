import pandas as pd, numpy as np, json
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
F=pd.read_pickle('F.pkl'); S=pd.read_pickle('S2.pkl')
cols=['f_p','f_miss','f_part','f_conc','f_disc']
sc=StandardScaler().fit(S[cols]); X=sc.transform(S[cols])
km=KMeans(5,n_init=50,random_state=0).fit(X)
# 군집 번호를 해석 순서로 재배열
P=S.assign(c=km.labels_).groupby('c')[['p_correct','partial_rate','wrong_concentration','discrimination']].mean()
order={}
order[P.partial_rate.idxmax()]='C4'
rest=P.drop(P.partial_rate.idxmax())
order[rest.wrong_concentration.idxmax()]='C3'
rest=rest.drop(rest.wrong_concentration.idxmax())
order[rest.p_correct.idxmax()]='C1'; rest=rest.drop(rest.p_correct.idxmax())
order[rest.discrimination.idxmax()]='C2'; rest=rest.drop(rest.discrimination.idxmax())
order[rest.index[0]]='C5'
NAMES={'C1':'기본 확인형','C2':'실력 구분형','C3':'오답 쏠림(함정)형','C4':'다단계 부분정답형','C5':'고난도·저변별형'}
S['cluster']=[order[l] for l in km.labels_]; S['cluster_name']=S.cluster.map(NAMES)
d=km.transform(X); S['dist_to_center']=d[np.arange(len(X)),km.labels_]
S['second_dist']=np.sort(d,axis=1)[:,1]; S['assign_margin']=(S.second_dist-S.dist_to_center).round(3)
# 비대상 문항
F['cluster']=None
F.loc[S.index,'cluster']=S.cluster
F.loc[F.cluster.isna()&(F.n<10),'cluster']='X1'
F.loc[F.cluster.isna()&(F.n_wrong_answered<3),'cluster']='X2'
F.loc[F.cluster.isna(),'cluster']='X3'
NAMES.update({'X1':'제외: 풀이 10건 미만','X2':'제외: 응답 있는 오답 3건 미만','X3':'제외: 변별도 계산 불가'})
F['cluster_name']=F.cluster.map(NAMES)
print(F.cluster.value_counts().sort_index())
print(F[F.cluster=='X2'][['p_correct','missing_rate','n']].describe().round(2))
print(F[F.cluster=='X3'][['n','n_wrong_answered']].head())
raw=['p_correct','missing_rate','partial_rate','wrong_concentration','discrimination','partial_first_ok_share','n','expected_count','q_len','needs_content_review','diagram_reference']
prof=S.groupby('cluster')[raw].mean().round(3)
prof['size']=S.cluster.value_counts(); prof['mc_share']=S.groupby('cluster').mc.mean().round(2)
prof['hard_label_share']=S.groupby('cluster').difficulty_label.apply(lambda x:(x=='hard').mean()).round(2)
prof['easy_label_share']=S.groupby('cluster').difficulty_label.apply(lambda x:(x=='easy').mean()).round(2)
prof['margin_median']=S.groupby('cluster').assign_margin.median().round(2)
prof.insert(0,'name',prof.index.map(NAMES))
print(prof.T.to_string())
print(pd.crosstab(S.cluster,S.semester_label))
kt=pd.crosstab(S.knowledge,S.cluster); print(kt)
S.to_pickle('S_final.pkl'); F.to_pickle('F_final.pkl'); prof.to_pickle('prof.pkl')
# 대표 문항: 중심에 가까운 3개
for c in sorted(S.cluster.unique()):
    print('\n###',c,NAMES[c])
    for i,r in S[S.cluster==c].nsmallest(3,'dist_to_center').iterrows():
        print(i,r.item_form,r.knowledge,'| p',round(r.p_correct,2),'miss',round(r.missing_rate,2),'part',round(r.partial_rate,2),'conc',round(r.wrong_concentration,2),'disc',round(r.discrimination,2),'| top wrong',r.top_wrong_response)
        print('   Q:',str(r.question_text)[:150].replace('\n',' '))
