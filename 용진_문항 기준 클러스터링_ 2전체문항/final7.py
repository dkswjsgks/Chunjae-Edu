import pandas as pd, numpy as np
from scipy.stats import beta
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score as ari
X=pd.read_pickle('X_eb2.pkl'); lg=lambda p:np.log(p/(1-p)); mu,sd=np.load('scale2.npy')
F=np.column_stack([lg(X.p_post),lg(X.miss_post),lg(X.part_post),X.conc_dev,X.z_post]); Fs=(F-mu)/sd
wt=np.sqrt(X.n.clip(lower=1).values.astype(float))
km=KMeans(7,n_init=100,random_state=0).fit(Fs,sample_weight=wt); lab=km.labels_
P=X.assign(c=lab).groupby('c')[['p_post','part_post','disc_post','conc_dev','n']].mean()
multi=X.assign(c=lab).groupby('c').multi.mean()
name={}
m=P[multi>0.5]; name[m.p_post.idxmax()]=('G4','다단계 기본형'); name[m.p_post.idxmin()]=('G5','다단계 고난도형')
s=P[multi<=0.5]
name[s.p_post.idxmax()]=('G1','기본 확인형'); s=s.drop(s.p_post.idxmax())
name[s.disc_post.idxmin()]=('G3','저변별형'); s=s.drop(s.disc_post.idxmin())
name[s.n.idxmax()]=('G7','고난도·오답분산형'); s=s.drop(s.n.idxmax())
name[s.p_post.idxmax()]=('G2','중난도 표준형'); s=s.drop(s.p_post.idxmax())
name[s.index[0]]=('G6','고난도 단일칸형')
X['군집']=[name[l][0] for l in lab]; X['군집명']=[name[l][1] for l in lab]
order={name[l][0]:l for l in name}
# 소속 확신도
rng=np.random.default_rng(0); T=300; cnt=np.zeros((len(X),7))
for t in range(T):
    d={f:np.clip(rng.beta(X[f+'_a'].clip(lower=1e-3),X[f+'_b'].clip(lower=1e-3)),1e-4,1-1e-4) for f in ['p','miss','part','conc']}
    z=rng.normal(X.z_post,np.sqrt(X.z_var))
    Ft=(np.column_stack([lg(d['p']),lg(d['miss']),lg(d['part']),d['conc']-X.conc_prior.values,z])-mu)/sd
    cnt[np.arange(len(X)),np.argmin(((Ft[:,None,:]-km.cluster_centers_[None])**2).sum(-1),axis=1)]+=1
X['소속확신도']=cnt[np.arange(len(X)),lab]/T
alt=cnt.copy(); alt[np.arange(len(X)),lab]=-1
X['차순위군집']=[name[l][0] for l in alt.argmax(1)]
# 오답 쏠림(함정) 의심 태그: 형태 기준선보다 오답이 한 값에 더 몰릴 사후확률
X['쏠림확률']=1-beta.cdf(X.conc_prior+0.10,X.conc_a,X.conc_b)
X['함정의심']=(X['쏠림확률']>=0.8)&(X.n_wrong_answered>=5)
print(X['군집'].value_counts().sort_index())
prof=X.groupby('군집').agg(군집명=('군집명','first'),문항수=('n','size'),정답률=('p_post','mean'),미응답률=('miss_post','mean'),일부정답률=('part_post','mean'),최빈오답비중=('conc_post','mean'),변별도=('disc_post','mean'),평균풀이수=('n','mean'),풀이10건이상_비율=('n',lambda s:(s>=10).mean()),다빈칸_비율=('multi','mean'),객관식_비율=('mc','mean'),소속확신도_중앙값=('소속확신도','median'),함정의심_문항수=('함정의심','sum')).round(3)
print(prof.T.to_string())
print(pd.crosstab(X['군집'],X['diff'])); print(pd.crosstab(X['군집'],X.discrimination_label)); print(pd.crosstab(X['군집'],X.semester_label))
print('함정의심',X['함정의심'].sum())
print(X[X['함정의심']].sort_values('쏠림확률',ascending=False)[['군집','n','n_wrong_answered','k_top_wrong','top_wrong_response','쏠림확률','knowledge']].head(12))
X['n_bin']=pd.cut(X.n,[-1,0,4,9,19,1000],labels=['0건','1-4건','5-9건','10-19건','20건+'])
print(X.groupby('n_bin',observed=True)['소속확신도'].median())
S=pd.read_pickle('S_final.pkl'); c=S.index
print('ARI vs earlier 612:',round(ari(S.cluster,X.loc[c,'군집']),3))
print(pd.crosstab(S.cluster_name,X.loc[c,'군집']))
X.to_pickle('X_final7.pkl'); prof.to_pickle('prof7.pkl')
