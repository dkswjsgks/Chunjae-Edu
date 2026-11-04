import pandas as pd, numpy as np
from sklearn.preprocessing import StandardScaler, QuantileTransformer
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, adjusted_rand_score as ari
S=pd.read_pickle('S.pkl')
lg=lambda p:np.log(p/(1-p))
n=S.n
S['f_p']=lg(S.p_correct)
S['f_miss']=lg((S.missing_rate*n+0.5)/(n+1))
S['f_part']=lg((S.partial_rate*n+0.5)/(n+1))
S['f_conc']=S.conc_adj
S['f_disc']=S.discrimination
sets={'5feat':['f_p','f_miss','f_part','f_conc','f_disc'],'4feat_noPartial':['f_p','f_miss','f_conc','f_disc']}
rng=np.random.default_rng(0)
for nm,cols in sets.items():
    X=StandardScaler().fit_transform(S[cols])
    Xq=QuantileTransformer(n_quantiles=200,output_distribution='normal',random_state=0).fit_transform(S[cols])
    print('==',nm, 'corr\n',S[cols].corr().round(2))
    for k in range(2,8):
        km=KMeans(k,n_init=30,random_state=0).fit(X)
        a=[ari(km.labels_,KMeans(k,n_init=10,random_state=b).fit(X[rng.choice(len(X),len(X))]).predict(X)) for b in range(30)]
        print(k,'sil',round(silhouette_score(X,km.labels_),3),'boot',round(np.mean(a),3),
              'vsQuant',round(ari(km.labels_,KMeans(k,n_init=30,random_state=0).fit(Xq).labels_),2),
              'vsWard',round(ari(km.labels_,AgglomerativeClustering(k).fit(X).labels_),2),
              'vsGMM',round(ari(km.labels_,GaussianMixture(k,n_init=3,random_state=0).fit(X).predict(X)),2),np.bincount(km.labels_))
S.to_pickle('S2.pkl')
