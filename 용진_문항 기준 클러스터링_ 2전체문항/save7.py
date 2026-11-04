import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import beta
O='/mnt/user-data/outputs/문항 기준 클러스터링_전체문항/'
X=pd.read_pickle('X_final7.pkl'); prof=pd.read_pickle('prof7.pkl'); S=X.attrs.get('strength',{})
X['쏠림근거']=(1-beta.cdf(X.conc_prior,X.conc_a,X.conc_b)>=0.9)&(X.n_wrong_answered>=5)
nz=lambda k,n: np.where(n>0,k/n.where(n>0,1),np.nan)
R=pd.DataFrame({
 '학기':X.semester_label,'지식':X.knowledge,'토픽':X.topic,'문항형태':X.item_form,'난이도_원본라벨':X.difficulty_label,'변별도_원본라벨':X.discrimination_label,
 '입력칸수':X.expected_count,'입력칸수_미확인':X.expected_count_unknown,'분석_풀이수':X.n.astype(int),
 '관측_정답률':nz(X.k_correct,X.n),'보정_정답률':X.p_post,'관측_미응답률':nz(X.k_missing,X.n),'보정_미응답률':X.miss_post,
 '관측_일부정답률':nz(X.k_partial,X.n),'보정_일부정답률':X.part_post,'응답있는_오답수':X.n_wrong_answered.astype(int),
 '관측_최빈오답비중':nz(X.k_top_wrong,X.n_wrong_answered),'보정_최빈오답비중':X.conc_post,'최빈오답':X.top_wrong_response,
 '관측_변별도':X.r_raw,'보정_변별도':X.disc_post,'정답률_데이터반영비중':X.p_dataweight,
 '군집':X['군집'],'군집명':X['군집명'],'소속확신도':X['소속확신도'],'차순위군집':X['차순위군집'],'오답쏠림_근거있음':X['쏠림근거'].astype(int),
 '내용검토필요':X.needs_content_review},index=X.index)
R.index.name='item_id'; R.round(3).to_csv(O+'문항별 군집 결과(전체 2197문항).csv',encoding='utf-8-sig')
prof.to_csv(O+'군집별 프로필.csv',encoding='utf-8-sig')
pd.crosstab(X.knowledge,X['군집']).to_csv(O+'지식별 군집 분포.csv',encoding='utf-8-sig')
kd=pd.read_pickle('kdiag2.pkl').rename(columns={'k':'군집수k','sil_all':'실루엣_전체','sil_rich':'실루엣_풀이10건이상','boot':'부트스트랩_ARI','min':'최소군집크기'}); kd.to_csv(O+'군집수 선정_진단.csv',index=False,encoding='utf-8-sig')
pd.DataFrame([
 ['정답률','난이도라벨×형태×입력칸',round(S['p'],1)],['미응답률','난이도라벨×형태×입력칸',round(S['miss'],1)],
 ['일부정답률','형태×입력칸',round(S['part'],1)],['최빈오답비중','형태×입력칸',round(S['conc'],1)],['변별도','변별도라벨',round(1/S['disc_tau2'],1)]],
 columns=['특징','사전 평균을 정한 집단','사전 강도(풀이 몇 건만큼의 정보인가)']).to_csv(O+'보정 강도 추정값.csv',index=False,encoding='utf-8-sig')
X[X['쏠림근거']][['knowledge','item_form','n','n_wrong_answered','k_top_wrong','top_wrong_response','군집']].to_csv(O+'오답쏠림 근거 문항.csv',encoding='utf-8-sig')
print(X['쏠림근거'].sum()); print(X[X['쏠림근거']][['knowledge','n_wrong_answered','k_top_wrong','top_wrong_response']])
# 차트
fp=[f for f in fm.findSystemFonts() if 'NotoSansCJK-Regular' in f][0]; fm.fontManager.addfont(fp)
plt.rcParams.update({'font.family':fm.FontProperties(fname=fp).get_name(),'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb','axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#b5b4ad'})
feat=['p_post','miss_post','part_post','conc_post','disc_post']; fl=['정답률','미응답률','일부 정답률','최빈 오답 비중','변별도']
M=X.groupby('군집')[feat].mean(); Z=(M-X[feat].mean())/X[feat].std()
cmap=LinearSegmentedColormap.from_list('d',['#2a78d6','#f0efec','#eb6834'])
fig,ax=plt.subplots(figsize=(10,4.8)); im=ax.imshow(Z.values,cmap=cmap,vmin=-2,vmax=2,aspect='auto')
ax.set_xticks(range(5),fl); ax.set_yticks(range(len(M)),[f'{c} {prof.loc[c,"군집명"]} ({prof.loc[c,"문항수"]})' for c in M.index])
for i in range(Z.shape[0]):
    for j in range(5): ax.text(j,i,f'{M.values[i,j]:.2f}',ha='center',va='center',fontsize=9.5)
for s in ax.spines.values(): s.set_visible(False)
cb=plt.colorbar(im,ax=ax,fraction=0.03); cb.set_label('전체 평균 대비(표준점수)',fontsize=8.5)
ax.set_title('전체 2,197문항 군집 프로필 (보정값 기준, k=7)',loc='left',fontsize=11.5)
plt.tight_layout(); plt.savefig(O+'차트1_군집 프로필.png',dpi=160)
fig,ax=plt.subplots(figsize=(8,5.5)); d=X[X.n>0]
sc=ax.scatter(d.k_correct/d.n,d.p_post,c=np.log1p(d.n),cmap=LinearSegmentedColormap.from_list('s',['#cde2fb','#104281']),s=12,alpha=0.8)
ax.plot([0,1],[0,1],color='#b5b4ad',lw=1,ls='--'); ax.set_xlabel('관측 정답률 (원자료)'); ax.set_ylabel('보정 정답률 (군집화에 사용)')
cb=plt.colorbar(sc,ax=ax); cb.set_label('풀이 수 (로그)',fontsize=8.5)
ax.set_title('정답률은 난이도 라벨 집단의 평균 쪽으로 강하게 보정됨 (가로 띠 = 라벨 집단)',loc='left',fontsize=11)
ax.grid(color='#e6e5e0'); ax.set_axisbelow(True); plt.tight_layout(); plt.savefig(O+'차트2_정답률 보정 효과.png',dpi=160)
c=X.groupby('n_bin',observed=True)['소속확신도'].median()
fig,ax=plt.subplots(figsize=(7,3.8)); ax.bar(c.index.astype(str),c.values,color='#2a78d6',width=0.6)
for i,v in enumerate(c.values): ax.text(i,v+0.01,f'{v:.2f}',ha='center',fontsize=9,color='#52514e')
ax.set_ylim(0,1); ax.set_xlabel('문항의 풀이 수'); ax.set_ylabel('소속 확신도 중앙값'); ax.yaxis.grid(True,color='#e6e5e0'); ax.set_axisbelow(True)
ax.set_title('풀이 수별 군집 소속 확신도',loc='left',fontsize=11.5); plt.tight_layout(); plt.savefig(O+'차트3_풀이수별 소속확신도.png',dpi=160)
