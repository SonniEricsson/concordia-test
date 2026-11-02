from typing import Any
import json
from collections.abc import Sequence
from concordia.components.agent.memory import AssociativeMemory
from concordia.components.agent import action_spec_ignored
from concordia.components.agent import memory as memory_component
from concordia.language_model import language_model
from concordia.typing import entity_component

MAX_QUERY_LENGTH = 100
MAX_LIMIT = 5

def extract_json(text: str) -> dict[str, Any]:
  """Extract the JSON object from a generated response."""
  try:
    content = json.loads(text)
  except json.JSONDecodeError as error:
    raise ValueError(f"Invalid JSON: {error}")

  if not isinstance(content, dict):
    raise ValueError("The action is not a JSON object.")

  return content

class MemoryRetrieval(
    action_spec_ignored.ActionSpecIgnored,
    entity_component.ComponentWithLogging,
):
  """Retrieve relevant memories from agent's observations."""

  def __init__(
      self,
      *,
      model: language_model.LanguageModel,
      components: Sequence[str],
      query_max_tokens: int = 500,
      pre_act_label: str = '\nRetrieved memories',
  ):
    super().__init__(pre_act_label)
    self._model = model
    self._components = components
    self._query_max_tokens = query_max_tokens

  def _make_pre_act_value(self) -> str:
    component_context = []

    for component in self._components:
      value = self.get_named_component_pre_act_value(component)
      component_context.append(f"{component}:\n{value}")

    current_context = "\n\n".join(component_context)

    prompt = (
      "Given the current context, decide whether memory retrieval is necessary "
      "for the determination of the agent's next action.\n"
      "Here is the agent's current context:\n\n"
      f"{current_context}\n\n"
      "Relevant observations would then be retrieved based on a query.\n"
      f"If a memory retrieval is necessary, return a query with less than {MAX_QUERY_LENGTH} words, "
      "containing detailed information, such as the names of relevant people or tasks.\n"
      "Add a limit as well, to set the max number of returned observations.\n"
      f"The limit should be between 1 and {MAX_LIMIT}"
      "Return one JSON object without Markdown formatting:\n"
      '{"query": "...", "limit": 2}\n'
      "If memory retrieval is not necessary, return this:\n"
      '{"query": null}'
    )

    response = self._model.sample_text(
      prompt,
      reasoning_effort="low",
      max_tokens=self._query_max_tokens
    )

    try:
      response_json = extract_json(response)

      query = response_json.get("query")
      limit = response_json.get("limit")

      if query != None:
        if not isinstance(query, str) or query == "" or len(query.split()) > MAX_QUERY_LENGTH:
          raise ValueError(f"Query is not a valid string with less than {MAX_QUERY_LENGTH}.")
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
          raise ValueError("Limit is not a valid integer.")
    except ValueError as err:
      retrieved_memory = {
        "query": None,
        "memories": [],
        "error": str(err),
      }
    else:
      if isinstance(query, str):
        memory = self.get_entity().get_component(
            memory_component.DEFAULT_MEMORY_COMPONENT_KEY,
            type_=memory_component.AssociativeMemory,
        )

        retrieved_memory = {
          "query": query,
          "memory": memory.retrieve_associative(query, limit),
        }
      else:
        retrieved_memory = {
          "query": None,
          "memory": [],
        }

    result = (
      "Historical observations from memory retrieval:\n"
      + json.dumps(retrieved_memory, indent=2)
    )

    self._logging_channel({
      "Key": self._pre_act_label,
      "Value": result,
      "Query": retrieved_memory.get("query"),
    })

    return result
