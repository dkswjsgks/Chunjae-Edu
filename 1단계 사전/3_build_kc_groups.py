"""
[1단계 사전 / 3 KC 묶음] 형식 차이만 있는 KC를 묶은 버전을 KC.csv의 kc_group, kc_group_name에 채운다. LLM을 쓰지 않는다.

실행 (레포 루트에서):  python "1단계 사전/3_build_kc_groups.py"
  2_import_eedi_kc_dictionary.py를 다시 실행하면 kc_group이 비므로 이 파일도 다시 실행한다.

입력: 사전/KC.csv
출력: 사전/KC.csv (kc_group = KG-<번호>, kc_group_name)

쓰임: 2단계·3단계의 kc_size=group 실행은 kc_id 대신 kc_group을 KC로 쓴다(Q행렬 KC 열, AFM KC).
     Eedi KC가 수의 개수·소수/분수·부등호 표기 같은 형식 차이까지 나뉘어 있어, 문항당 응답이 적은
     우리 데이터에서 KC가 너무 잘게 나뉘는 역효과를 비교하기 위한 버전이다.

묶음 기준: 같은 연산·같은 판단을 쓰고 수의 개수, 수의 종류(정수·소수·분수), 표기(부등호)만 다른 KC를 묶는다.
GROUPS는 초안이다. 팀 검토 후 이 표를 직접 고친다. 표에 없는 KC는 혼자 한 묶음이 된다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "공통"))

import data_io  # noqa: E402
import paths  # noqa: E402

# (묶음 이름, [kc_id, ...])
GROUPS = [
    # 유리수의 덧셈과 뺄셈의 혼합계산
    ("음수가 포함된 덧셈", ["KC-E246", "KC-E247", "KC-E248", "KC-E3194"]),
    ("음수가 포함된 뺄셈", ["KC-E255", "KC-E256", "KC-E3115", "KC-E3328"]),
    ("덧셈·뺄셈에서 빈칸의 수 구하기", ["KC-E252", "KC-E261", "KC-E262", "KC-E3241"]),
    ("분수의 덧셈", ["KC-E424", "KC-E425", "KC-E426", "KC-E427", "KC-E430"]),
    ("분수의 뺄셈", ["KC-E432", "KC-E433", "KC-E434", "KC-E435"]),
    ("대분수의 덧셈과 뺄셈", ["KC-E428", "KC-E429", "KC-E436", "KC-E437"]),
    # 정수와 유리수의 대소 관계
    ("정수의 대소 비교", ["KC-E234", "KC-E235", "KC-E236", "KC-E237", "KC-E3327", "KC-E3786"]),
    ("음의 소수·분수의 대소 비교", ["KC-E238", "KC-E239", "KC-E241", "KC-E245"]),
    ("음수의 수직선 위치 찾기", ["KC-E230", "KC-E233", "KC-E243"]),
    ("음수를 0으로부터의 거리로 이해", ["KC-E3817", "KC-E3818"]),
    ("절댓값 구하기와 비교", ["KC-E3325", "KC-E3781", "KC-E3784", "KC-E3785"]),
    ("반대수 구하기", ["KC-E3774", "KC-E3778", "KC-E3777"]),
    ("수직선에서 0을 지나 세기", ["KC-E226", "KC-E3326"]),
    ("양의 소수·분수의 대소 비교", ["KC-E297", "KC-E415"]),
]


def assign(kc):
    member = {}
    for name, ids in GROUPS:
        for k in ids:
            if k in member:
                raise ValueError(f"{k}가 두 묶음에 있음: {member[k]}, {name}")
            member[k] = name
    unknown = set(member) - set(kc.kc_id)
    if unknown:
        raise ValueError(f"KC.csv에 없는 kc_id: {sorted(unknown)}")
    knowledge = dict(zip(kc.kc_id, kc.knowledge_id))
    for name, ids in GROUPS:
        if len({knowledge[k] for k in ids}) > 1:
            raise ValueError(f"묶음 '{name}'이 두 지식에 걸침")

    kc = kc.copy()
    kc["kc_group_name"] = [member.get(k, n) for k, n in zip(kc.kc_id, kc.kc_name_ko)]
    order = {n: i for i, n in enumerate(dict.fromkeys(kc.kc_group_name))}
    kc["kc_group"] = [f"KG-{order[n] + 1:02d}" for n in kc.kc_group_name]
    return kc


def main():
    kc = assign(data_io.load_dictionary("KC"))
    kc.to_csv(paths.DICTIONARY / "KC.csv", index=False, encoding="utf-8-sig")
    size = kc.groupby(["knowledge_name", "kc_group", "kc_group_name"]).kc_id.size().rename("n_kc").reset_index()
    for name, g in size.groupby("knowledge_name"):
        print(f"{name}: KC {g.n_kc.sum()}개 → 묶음 {len(g)}개")
    print(size[size.n_kc > 1].to_string(index=False))


if __name__ == "__main__":
    main()
