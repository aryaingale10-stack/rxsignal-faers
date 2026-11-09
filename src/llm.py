"""Layer 4 (optional): ask an LLM to suggest the generic name for names RxNorm could not match.

The LLM only *suggests*. Every suggestion is then verified with an exact RxNorm lookup, so a
hallucinated drug name can never enter the data.

Set ONE of these environment variables to enable it:
    ANTHROPIC_API_KEY   (model: LLM_MODEL, default claude-haiku-5-5)
    OPENAI_API_KEY      (model: LLM_MODEL, default gpt-4o-mini)
"""
import json
import os
import re

import requests

PROMPT = """You are a pharmacist normalizing drug names from FDA adverse event reports.
For each input string, give the generic (active ingredient) name in English, or null if the
string is not a recognizable drug (e.g. a misspelling you cannot resolve, a lab test, a device,
or a vague phrase). Fix obvious misspellings. Translate foreign brand names when you are sure.
For combination products, join generic names with " / ".

Return ONLY a JSON object mapping each input string exactly to its answer.

Inputs:
{items}"""


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def _call(prompt: str) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.environ.get("LLM_MODEL", "claude-haiku-5-5"), "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=120,
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"])
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def suggest_generics(names: list[str], batch_size: int = 50) -> dict[str, str | None]:
    """Returns {input name: suggested generic or None}."""
    out = {}
    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        prompt = PROMPT.format(items="\n".join(f"- {n}" for n in batch))
        try:
            text = _call(prompt)
            text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
            answers = json.loads(text[text.find("{"): text.rfind("}") + 1])
        except Exception as e:  # keep going; unresolved names just stay unresolved
            print(f"    LLM batch {i // batch_size + 1} failed: {e}")
            answers = {}
        for n in batch:
            v = answers.get(n)
            out[n] = v.strip().lower() if isinstance(v, str) and v.strip() else None
        print(f"    LLM suggestions: {min(i + batch_size, len(names))}/{len(names)}")
    return out
