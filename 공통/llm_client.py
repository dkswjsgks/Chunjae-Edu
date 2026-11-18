"""
GPT·Claude 호출을 한 형식으로 한다. LLM을 쓰는 모든 run.py는 이 파일만 쓴다.

함수
  load_prompt(path, stage, **vars)   prompt.md를 읽어 {"system": ..., "user": ..., <다른 섹션>: ...}을 돌려준다
  chat(provider, system, user, schema=None, model=None, cache_dir=None, sample=0)
                                     한 번 호출. schema(JSON Schema)를 주면 구조화 출력으로 받아 parsed에 넣는다
  score_yes(provider, system, user, model=None, n_samples=5, cache_dir=None)
                                     "Yes/No" 질문의 Yes 점수. GPT는 토큰 확률, Claude는 n번 샘플링한 Yes 비율

prompt.md 형식
  ## system      항상 쓰는 시스템 프롬프트
  ## user        사용자 프롬프트. {{변수}} 자리에 값이 들어간다
  ## 원칙        prompt_stage >= 2 이면 system 뒤에 붙는다 (과잉 태깅 방지 등)
  ## 예시        prompt_stage >= 3 이면 system 뒤에 붙는다 (사람이 검수한 예시)
  ## <그 밖>     run.py가 이름으로 꺼내 쓰는 추가 템플릿

.env (레포 루트, 커밋하지 않음. 형식은 .env.example)
  OPENAI_API_KEY, OPENAI_MODEL, OPENAI_REASONING_EFFORT, OPENAI_MAX_OUTPUT_TOKENS, OPENAI_STORE, OPENAI_BASE_URL,
  OPENAI_SCORE_MODEL (토큰 확률 점수용. 추론 모델은 logprobs를 주지 않으므로 비추론 모델)
  ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_EFFORT, ANTHROPIC_MAX_TOKENS, ANTHROPIC_FALLBACK

주의
  - 학생 ID를 프롬프트에 넣지 않는다.
  - Claude는 토큰 확률을 주지 않고, 현재 모델은 temperature도 받지 않는다. 점수는 샘플링 비율이나
    모델이 직접 답한 확률이며 GPT 토큰 확률과 의미가 다르다. 두 점수를 섞지 않는다(score_method 열로 구분).
  - Claude 호출은 기본으로 서버 측 fallback(거절 시 다른 모델로 재실행)을 켠다. 끄려면 ANTHROPIC_FALLBACK=off.
"""

import hashlib
import json
import math
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PROVIDERS = ("openai", "anthropic")
_VAR = re.compile(r"\{\{(\w+)\}\}")


class LLMRefusal(RuntimeError):
    """모델이 응답을 거절했다(stop_reason=refusal)."""


def default_model(provider):
    if provider == "openai":
        return os.environ.get("OPENAI_MODEL", "")
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL") or "claude-opus-5-5"
    raise ValueError(f"provider는 {PROVIDERS} 중 하나: {provider}")


# ---------------------------------------------------------------- 프롬프트
def load_prompt(path, stage=1, **vars):
    text = Path(path).read_text(encoding="utf-8")
    sections, name = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            sections[name] = []
        elif name is not None:
            sections[name].append(line)
    sections = {k: "\n".join(v).strip() for k, v in sections.items()}
    if "system" not in sections or "user" not in sections:
        raise ValueError(f"{path}: '## system'과 '## user' 섹션이 필요하다")
    system = sections["system"]
    if stage >= 2 and sections.get("원칙"):
        system += "\n\n[원칙]\n" + sections["원칙"]
    if stage >= 3 and sections.get("예시"):
        system += "\n\n[예시]\n" + sections["예시"]
    out = {k: _render(v, vars) for k, v in sections.items() if k not in ("원칙", "예시")}
    out["system"] = _render(system, vars)
    return out


def _render(template, vars):
    """값이 없는 {{변수}}는 그대로 둔다(섹션마다 필요한 변수가 다르다). 보내기 전에 chat()이 검사한다."""
    def sub(m):
        if m.group(1) not in vars:
            return m.group(0)
        v = vars[m.group(1)]
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return _VAR.sub(sub, template)


# ---------------------------------------------------------------- 캐시
def _cache_get(cache_dir, key):
    if not cache_dir:
        return None
    p = Path(cache_dir) / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _cache_put(cache_dir, key, value):
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        (Path(cache_dir) / f"{key}.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]


# ---------------------------------------------------------------- 호출
def chat(provider, system, user, schema=None, model=None, cache_dir=None, sample=0):
    """sample: 같은 질문을 여러 번 샘플링할 때 캐시를 구분하는 번호."""
    left = set(_VAR.findall(system + user))
    if left:
        raise KeyError(f"프롬프트 변수에 값이 없다: {sorted(left)}")
    model = model or default_model(provider)
    if not model:
        raise RuntimeError(f"{provider} 모델이 비어 있다. .env의 OPENAI_MODEL / ANTHROPIC_MODEL을 채운다")
    key = _key(provider, model, system, user, schema, sample)
    hit = _cache_get(cache_dir, key)
    if hit is not None:
        return hit
    if provider == "openai":
        out = _chat_openai(model, system, user, schema)
    elif provider == "anthropic":
        out = _chat_anthropic(model, system, user, schema)
    else:
        raise ValueError(f"provider는 {PROVIDERS} 중 하나: {provider}")
    out["parsed"] = json.loads(out["text"]) if schema else None
    out.update(provider=provider, requested_model=model)
    _cache_put(cache_dir, key, out)
    return out


def _chat_openai(model, system, user, schema):
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)
    kw = dict(
        model=model,
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_output_tokens=int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS") or 16000),
        store=os.environ.get("OPENAI_STORE", "false").lower() == "true",
    )
    if os.environ.get("OPENAI_REASONING_EFFORT"):
        kw["reasoning"] = {"effort": os.environ["OPENAI_REASONING_EFFORT"]}
    if schema:
        kw["text"] = {"format": {"type": "json_schema", "name": "output", "schema": schema, "strict": True}}
    r = client.responses.create(**kw)
    if r.status != "completed":
        raise RuntimeError(f"OpenAI 응답 미완료: {r.status} {getattr(r, 'incomplete_details', '')}")
    return {"text": r.output_text, "model": r.model, "request_id": r.id,
            "usage": r.usage.model_dump() if r.usage else {}}


def _chat_anthropic(model, system, user, schema):
    import anthropic
    client = anthropic.Anthropic()
    output_config = {"effort": os.environ.get("ANTHROPIC_EFFORT") or "high"}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    kw = dict(model=model, max_tokens=int(os.environ.get("ANTHROPIC_MAX_TOKENS") or 16000),
              system=system, messages=[{"role": "user", "content": user}], output_config=output_config)
    fallback = os.environ.get("ANTHROPIC_FALLBACK", "default")
    if fallback != "off":
        r = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks=fallback, **kw)
    else:
        r = client.messages.create(**kw)
    if r.stop_reason == "refusal":
        detail = r.stop_details.category if r.stop_details else None
        raise LLMRefusal(f"Claude 거절: {detail}")
    if r.stop_reason == "max_tokens":
        raise RuntimeError("Claude 응답이 max_tokens에서 잘렸다. ANTHROPIC_MAX_TOKENS를 늘린다")
    text = "".join(b.text for b in r.content if b.type == "text")
    return {"text": text, "model": r.model, "request_id": r._request_id, "usage": r.usage.model_dump()}


# ---------------------------------------------------------------- 점수
_YES_NO_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": ["Yes", "No"]}},
    "required": ["answer"],
    "additionalProperties": False,
}


def score_yes(provider, system, user, model=None, n_samples=5, cache_dir=None):
    """user는 "Yes 또는 No로만 답하라"로 끝나야 한다. 돌려주는 값: {"score", "score_method", "detail"}."""
    left = set(_VAR.findall(system + user))
    if left:
        raise KeyError(f"프롬프트 변수에 값이 없다: {sorted(left)}")
    if provider == "openai":
        return _score_logprob(system, user, model or os.environ.get("OPENAI_SCORE_MODEL") or default_model("openai"),
                              cache_dir)
    answers = [chat(provider, system, user, schema=_YES_NO_SCHEMA, model=model, cache_dir=cache_dir,
                    sample=i)["parsed"]["answer"] for i in range(n_samples)]
    return {"score": answers.count("Yes") / n_samples, "score_method": f"sampling_n{n_samples}", "detail": answers}


def _score_logprob(system, user, model, cache_dir):
    key = _key("logprob", model, system, user)
    hit = _cache_get(cache_dir, key)
    if hit is not None:
        return hit
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)
    r = client.chat.completions.create(
        model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_completion_tokens=1, logprobs=True, top_logprobs=10)
    tops = r.choices[0].logprobs.content[0].top_logprobs
    p = {"Yes": 0.0, "No": 0.0}
    for t in tops:
        tok = t.token.strip().lower()
        if tok in ("yes", "no"):
            p[tok.capitalize()] += math.exp(t.logprob)
    total = p["Yes"] + p["No"]
    out = {"score": p["Yes"] / total if total else None, "score_method": "logprob",
           "detail": {t.token: t.logprob for t in tops}}
    _cache_put(cache_dir, key, out)
    return out
