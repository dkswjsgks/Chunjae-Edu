import pandas as pd, numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score as ari
X=pd.read_pickle('X_eb2.pkl'); lg=lambda p:np.log(p/(1-p))
F=np.column_stack([lg(X.p_post),lg(X.miss_post),lg(X.part_post),X.conc_dev,X.z_post])
wt=np.sqrt(X.n.clip(lower=1).values.astype(float))
mu=np.average(F,axis=0,weights=wt); sd=np.sqrt(np.average((F-mu)**2,axis=0,weights=wt)); Fs=(F-mu)/sd
np.save('scale2.npy',np.vstack([mu,sd]))
rich=(X.n>=10).values; rng=np.random.default_rng(0); rows=[]
for k in range(3,10):
    km=KMeans(k,n_init=30,random_state=0).fit(Fs,sample_weight=wt)
    a=[ari(km.labels_,KMeans(k,n_init=10,random_state=b).fit(Fs[(idx:=rng.choice(len(Fs),len(Fs),p=wt/wt.sum()))]).predict(Fs)) for b in range(30)]
    rows.append({'k':k,'sil_all':round(silhouette_score(Fs,km.labels_,sample_size=2000,random_state=0),3),'sil_rich':round(silhouette_score(Fs[rich],km.labels_[rich]),3),'boot':round(np.mean(a),3),'min':np.bincount(km.labels_).min()})
    print(rows[-1])
pd.DataFrame(rows).to_pickle('kdiag2.pkl')
