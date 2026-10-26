"""Class for Language models from DFKI."""

from collections.abc import Collection, Sequence
from typing import Any

from concordia.language_model import language_model
from openai import OpenAI

_MAX_MULTIPLE_CHOICE_ATTEMPTS = 5

# Similar to base_gpt_model.py
class MlxModel(language_model.LanguageModel):
  """Base class for models from DFKI."""

  def __init__(self,
      model_name: str,
      base_url: str
  ):
    self._model_name = model_name
    self._client = OpenAI(
        base_url=base_url,
        api_key="not-required",
        max_retries=0,
    )

  def sample_text(
      self,
      prompt: str,
      *,
      reasoning_effort: str = "low",
      max_tokens: int = language_model.DEFAULT_MAX_TOKENS,
      terminators: Collection[str] = language_model.DEFAULT_TERMINATORS,
      temperature: float = language_model.DEFAULT_TEMPERATURE,
      top_p: float = language_model.DEFAULT_TOP_P,
      top_k: int = language_model.DEFAULT_TOP_K,
      timeout: float = language_model.DEFAULT_TIMEOUT_SECONDS,
      seed: int | None = None,
  ) -> str:

    response = self._client.chat.completions.create(
        model=self._model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        #stop=list(terminators) or None,
        stop=None,
        timeout=max(timeout, 300.0),
        seed=seed,
        #extra_body={
        #    "enable_thinking": False,
        #    "top_k": top_k,
        #},
        reasoning_effort=reasoning_effort,
        #extra_body={"top_k": top_k}
    )

    return (response.choices[0].message.content or "").strip()

  def sample_choice(
      self,
      prompt: str,
      responses: Sequence[str],
      *,
      seed: int | None = None,
  ) -> tuple[int, str, dict[str, Any]]:
    prompt = (
        prompt
        + '\nRespond EXACTLY with one of the following strings:\n'
        + '\n'.join(responses)
        + '.'
    )

    sample = ''
    answer = ''
    for _ in range(_MAX_MULTIPLE_CHOICE_ATTEMPTS):
      answer = self.sample_text(
          prompt,
          #temperature=0,
          reasoning_effort="medium",
          seed=seed,
      )

      try:
        idx = responses.index(answer)
      except ValueError:
        continue
      else:
        return idx, responses[idx], {}

    raise language_model.InvalidResponseError((
        f'Too many multiple choice attempts.\nLast attempt: {sample}, '
        + f'extracted: {answer}'
    ))
