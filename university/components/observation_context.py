"""A rolling conversation summary alongside a recent observation history."""

from typing import cast

from concordia.components.agent import action_spec_ignored
from concordia.language_model import language_model
from concordia.typing import entity_component

# Similarily to components\agents\observation.py
class ObservationContext(
    action_spec_ignored.ActionSpecIgnored,
    entity_component.ComponentWithLogging,
):
  """A component that summarizes older observations when the context history gets too large."""

  def __init__(
      self,
      model: language_model.LanguageModel,
      *,
      history_length: int = 30,
      batch_size: int = 20,
      summary_max_tokens: int = 400,
      pre_act_label: str = '\nConversation history',
  ):
    super().__init__(pre_act_label)
    parameters = {
      "history_length": history_length,
      "batch_size": batch_size,
      "summary_max_tokens": summary_max_tokens,
    }
    for name, value in parameters.items():
      if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")

    # Number of recent observations that are kept fully.
    self._history_length = history_length
    # Number of older observations that are being summarized.
    self._batch_size = batch_size
    self._summary_max_tokens = summary_max_tokens

    self._model = model

    self._summary = ""
    self._recent_observations= []
    # Total number of summarized observations.
    self._summarized_obs_count = 0

  def pre_observe(self, observation: str) -> str:
    """Update recent observations before summarizing."""
    observations = observation.split('\n\n\n')
    for observation in observations:
      if observation:
        self._recent_observations.append(observation)
    return ''

  def _make_pre_act_value(self) -> str:
    """Summarize older observations before agent acts."""
    new_summarized_obs_count = 0

    # Summarize observations until the context history is small enough.
    while len(self._recent_observations) > (
        self._history_length + self._batch_size
    ):
      # Get the oldest observations using batch_size
      old_observations = self._recent_observations[:self._batch_size]
      prompt = (
          "Summarize the old observations for this agent.\n"
          "The summary should be concise, and not miss any important information.\n"
          "Distinguish between claims and confirmed university facts.\n"
          "Do not invent information.\n"
          "Your goal is to update the conversation summary using the previous summary and older observations.\n"
          "The updated summary should have at most 300 words.\n\n"
          f"This is the previous summary:\n{self._summary}\n\n"
          "These are the old observations that you should summarize:\n"
          + "\n\n".join(old_observations)
      )

      # Generate summary of previous summary and oldest observations.
      new_summary = self._model.sample_text(
          prompt,
          reasoning_effort="medium",
          max_tokens=self._summary_max_tokens,
      )
      if not new_summary:
        raise language_model.InvalidResponseError(
            "Observation summarization returned an empty summary."
        )

      self._summary = new_summary
      del self._recent_observations[:self._batch_size]
      new_summarized_obs_count += self._batch_size

    self._summarized_obs_count += new_summarized_obs_count
    result = (
        "Summary of older observations:\n"
        f"{self._summary}\n\n"
        "Recent observations:\n"
        + '\n\n'.join(self._recent_observations)
    )
    self._logging_channel({
        "Key": self._pre_act_label,
        "Summary": self._summary,
        "Value": result,
        "Recent observations": len(self._recent_observations),
        "Summarized observation count": new_summarized_obs_count,
        "Total summarized observation count": self._summarized_obs_count,
    })
    return result

  def get_state(self) -> entity_component.ComponentState:
    return {
        "summary": self._summary,
        "recent_observations": list(self._recent_observations),
        "summarized_obs_count": self._summarized_obs_count,
    }

  def set_state(self, state: entity_component.ComponentState) -> None:
    self._summary = cast(str, state["summary"])
    self._recent_observations = list(
        cast(list[str], state["recent_observations"])
    )
