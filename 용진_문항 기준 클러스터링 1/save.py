import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, adjusted_rand_score as ari
O='/mnt/user-data/outputs/문항 기준 클러스터링/'
S=pd.read_pickle('S_final.pkl'); F=pd.read_pickle('F_final.pkl'); prof=pd.read_pickle('prof.pkl')
it=pd.read_csv('/mnt/user-data/uploads/전처리 결과/문항 정보_전처리.csv',encoding='utf-8-sig')
# 1) 문항별 결과 (문항 파일 전체 2,197개 기준)
R=it[['item_id','semester_label','item_form','difficulty_label','discrimination_label']].set_index('item_id')
R=R.join(F[['knowledge','topic','n','p_correct','missing_rate','partial_rate','n_wrong_answered','wrong_concentration','top_wrong_response','discrimination','cluster','cluster_name']])
R=R.join(S[['assign_margin']])
R['cluster']=R.cluster.fillna('X1'); R['cluster_name']=R.cluster_name.fillna('제외: 풀이 10건 미만'); R['n']=R.n.fillna(0).astype(int)
R=R.rename(columns={'semester_label':'학기','item_form':'문항형태','difficulty_label':'난이도_원본라벨','discrimination_label':'변별도_원본라벨','knowledge':'지식','topic':'토픽','n':'분석_풀이수','p_correct':'정답률_보정','missing_rate':'전체미응답률','partial_rate':'일부정답률','n_wrong_answered':'응답있는_오답수','wrong_concentration':'최빈오답_비중','top_wrong_response':'최빈오답','discrimination':'실측_변별도','cluster':'군집','cluster_name':'군집명','assign_margin':'배정_여유도'})
R.round(3).to_csv(O+'문항별 군집 결과.csv',encoding='utf-8-sig')
# 2) 프로필
pk=prof.rename(columns={'name':'군집명','size':'문항수','p_correct':'정답률_보정','missing_rate':'전체미응답률','partial_rate':'일부정답률','wrong_concentration':'최빈오답_비중','discrimination':'실측_변별도','partial_first_ok_share':'부분정답중_첫칸정답비율','n':'평균_풀이수','expected_count':'평균_입력칸수','q_len':'평균_문제길이','needs_content_review':'내용검토필요_비율','diagram_reference':'그림언급_비율','mc_share':'객관식_비율','hard_label_share':'hard라벨_비율','easy_label_share':'easy라벨_비율','margin_median':'배정여유도_중앙값'})
pk.to_csv(O+'군집별 프로필.csv',encoding='utf-8-sig')
pd.crosstab(S.knowledge,S.cluster_name).to_csv(O+'지식별 군집 분포.csv',encoding='utf-8-sig')
# 3) k 진단
cols=['f_p','f_miss','f_part','f_conc','f_disc']; X=StandardScaler().fit_transform(S[cols]); rng=np.random.default_rng(0); rows=[]
for k in range(2,8):
    km=KMeans(k,n_init=30,random_state=0).fit(X)
    a=[ari(km.labels_,KMeans(k,n_init=10,random_state=b).fit(X[rng.choice(len(X),len(X))]).predict(X)) for b in range(30)]
    rows.append({'군집수k':k,'실루엣':round(silhouette_score(X,km.labels_),3),'부트스트랩_ARI':round(np.mean(a),3),'Ward일치_ARI':round(ari(km.labels_,AgglomerativeClustering(k).fit(X).labels_),2),'GMM일치_ARI':round(ari(km.labels_,GaussianMixture(k,n_init=3,random_state=0).fit(X).predict(X)),2),'최소군집크기':np.bincount(km.labels_).min()})
pd.DataFrame(rows).to_csv(O+'군집수 선정_진단.csv',index=False,encoding='utf-8-sig'); print(pd.DataFrame(rows))
# 4) 차트
fp=[f for f in fm.findSystemFonts() if 'NotoSansCJK-Regular' in f][0]; fm.fontManager.addfont(fp)
plt.rcParams.update({'font.family':fm.FontProperties(fname=fp).get_name(),'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb','axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#b5b4ad'})
feat=['p_correct','missing_rate','partial_rate','wrong_concentration','discrimination']
fl=['정답률','전체 미응답률','일부 정답률','최빈 오답 비중','실측 변별도']
M=S.groupby('cluster')[feat].mean(); Z=(M-S[feat].mean())/S[feat].std()
cmap=LinearSegmentedColormap.from_list('d',['#2a78d6','#f0efec','#eb6834'])
fig,ax=plt.subplots(figsize=(9.5,4)); im=ax.imshow(Z.values,cmap=cmap,vmin=-2,vmax=2,aspect='auto')
ax.set_xticks(range(5),fl); ax.set_yticks(range(5),[f'{c} {prof.loc[c,"name"]} ({prof.loc[c,"size"]})' for c in M.index])
for i in range(5):
    for j in range(5): ax.text(j,i,f'{M.values[i,j]:.2f}',ha='center',va='center',fontsize=9.5)
for s in ax.spines.values(): s.set_visible(False)
cb=plt.colorbar(im,ax=ax,fraction=0.03); cb.set_label('전체 평균 대비(표준점수)',fontsize=8.5)
ax.set_title('문항 군집 프로필 (612문항, k=5) — 숫자는 군집 평균, 색은 평균 대비 높고 낮음',loc='left',fontsize=11)
plt.tight_layout(); plt.savefig(O+'차트1_군집 프로필.png',dpi=160)
C=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4']
fig,ax=plt.subplots(figsize=(8,5.5))
for c,col in zip(sorted(S.cluster.unique()),C):
    d=S[S.cluster==c]; ax.scatter(d.p_correct,d.discrimination,s=14+d.n*0.6,color=col,alpha=0.75,edgecolor='#fcfcfb',linewidth=0.8,label=f'{c} {prof.loc[c,"name"]}')
ax.set_xlabel('정답률(보정)'); ax.set_ylabel('실측 변별도'); ax.grid(color='#e6e5e0'); ax.set_axisbelow(True); ax.legend(frameon=False,fontsize=9,loc='lower right')
ax.set_title('정답률 × 변별도 평면의 문항 분포 (점 크기 = 풀이 수)',loc='left',fontsize=11.5)
plt.tight_layout(); plt.savefig(O+'차트2_정답률x변별도 분포.png',dpi=160)
print(R.군집.value_counts())
