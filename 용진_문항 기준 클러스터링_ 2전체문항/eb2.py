import pandas as pd, numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import betaln
X=pd.read_pickle('X_eb.pkl')
def bb_mle(k,n,mu):
    o=n>=1; k,n,mu=k[o].values,n[o].values,np.clip(mu[o].values,1e-3,1-1e-3)
    f=lambda lm:-np.sum(betaln(k+mu*np.exp(lm),n-k+(1-mu)*np.exp(lm))-betaln(mu*np.exp(lm),(1-mu)*np.exp(lm)))
    return float(np.exp(minimize_scalar(f,bounds=(np.log(0.5),np.log(5000)),method='bounded').x))
def grp_mean(k,n,grp,minn=1):
    o=n>=minn; mu_g=(k[o].groupby(grp[o]).sum()+0.5)/(n[o].groupby(grp[o]).sum()+1)
    return grp.map(mu_g).fillna((k[o].sum()+0.5)/(n[o].sum()+1))
S={}
X['p_prior']=grp_mean(X.k_correct,X.n,X.g_pm); S['p']=bb_mle(X.k_correct,X.n,X.p_prior)
X['miss_prior']=grp_mean(X.k_missing,X.n,X.g_pm); S['miss']=bb_mle(X.k_missing,X.n,X.miss_prior)
X['part_prior']=grp_mean(X.k_partial,X.n,X.g_c); S['part']=bb_mle(X.k_partial,X.n,X.part_prior)
X['conc_prior']=grp_mean(X.k_top_wrong,X.n_wrong_answered,X.g_c); S['conc']=bb_mle(X.k_top_wrong,X.n_wrong_answered,X.conc_prior)
for f,k,n in [('p','k_correct','n'),('miss','k_missing','n'),('part','k_partial','n'),('conc','k_top_wrong','n_wrong_answered')]:
    m=S[f]; X[f+'_a']=X[k]+m*X[f+'_prior']; X[f+'_b']=X[n]-X[k]+m*(1-X[f+'_prior'])
    X[f+'_post']=X[f+'_a']/(X[f+'_a']+X[f+'_b']); X[f+'_dataweight']=X[n]/(X[n]+m)
# 변별도: 기업 변별도 라벨을 사전집단으로, 정규-정규 모형으로 tau2 최대우도
z=np.arctanh(X.r_raw.clip(-.99,.99)); w=(X.n_pairs-3)
ok=z.notna()&(w>=1)
dl=X.discrimination_label.fillna('unknown')
X['z_prior']=dl.map(z[ok].groupby(dl[ok]).mean()).fillna(z[ok].mean())
r=(z-X.z_prior)[ok]; v=1/w[ok]
nll=lambda lt: 0.5*np.sum(np.log(v+np.exp(lt))+r**2/(v+np.exp(lt)))
tau2=float(np.exp(minimize_scalar(nll,bounds=(np.log(1e-5),np.log(1)),method='bounded').x))
prec=np.where(ok,w,0); X['z_post']=(prec*z.fillna(0)+X.z_prior/tau2)/(prec+1/tau2); X['z_var']=1/(prec+1/tau2)
X['disc_post']=np.tanh(X.z_post); X['disc_dataweight']=prec/(prec+1/tau2)
S['disc_tau2']=tau2
print({k:round(v,4) for k,v in S.items()})
print('discrimination prior pairs-equivalent',round(1/tau2,1))
X['conc_dev']=X.conc_post-X.conc_prior   # 형태 집단 기준선 대비 오답 쏠림(보정)
X.attrs['strength']=S
X.to_pickle('X_eb2.pkl')
for f in ['p','miss','part','conc','disc']:
    print(f, 'median data weight (n>=10):',round(X.loc[X.n>=10,f+'_dataweight'].median(),3),' (n<10):',round(X.loc[X.n<10,f+'_dataweight'].median(),3))
