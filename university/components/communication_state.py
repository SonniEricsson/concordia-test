import copy
import json
from typing import Any, cast, Literal
from concordia.typing import entity_component
from university.components.academic_calendar import AcademicCalendar

DEFAULT_MAX_MESSAGE_WORDS = 100
STATUS_OPTIONS = Literal["succeeded", "rejected"]

def extract_json(text: str) -> dict[str, Any]:
  """Extract the JSON object from a generated response."""
  try:
    content = json.loads(text)
  except json.JSONDecodeError as error:
    raise ValueError(f"Invalid JSON: {error}")

  if not isinstance(content, dict):
    raise ValueError("The action is not a JSON object.")

  return content

class CommunicationState(
    entity_component.ContextComponent,
    entity_component.ComponentWithLogging,
):
  """A component that represents the private communication between university agents."""
  def __init__(
      self,
      *,
      agents: list[str],
      calendar: AcademicCalendar,
      max_words: int = DEFAULT_MAX_MESSAGE_WORDS,
      pre_act_label: str = "\nCommunication state",
  ):
    super().__init__()
    self._pre_act_label = pre_act_label
    self._agents = agents
    self._calendar = calendar
    self._max_words = max_words

    # Contains all messages in order.
    messages = []
    # Contains all sent messages for each agent.
    sent_messages = {}

    for agent in agents:
      sent_messages[agent] = {}
      for target in agents:
        if agent != target:
          # Contains all messages that agent has sent to target.
          sent_messages[agent][target] = []

    self._state: dict[str, Any] = {
      "messages": messages,
      "sent_messages": sent_messages,
      "next_message_id": 1,
    }

  def record_event(
      self,
      *,
      week: int,
      sender: str,
      recipient: str | None = None,
      content: str | None = None,
      status: STATUS_OPTIONS,
      failure_type: str | None = None,
  ) -> None:
    """Record message and add it to the list."""
    message = {
      #"message_id": len(self._messages) + 1,
      "message_id": self._state["next_message_id"],
      "week": week,
      "sender": sender,
      "recipient": recipient,
      "content": content,
      "status": status,
      "failure_type": failure_type,
    }

    self._state["messages"].append(message)
    if status == "succeeded":
      self._state["sent_messages"][sender][recipient].append(message)
    self._state["next_message_id"] += 1

    self._logging_channel({
        "Key": self._pre_act_label,
        "Summary": f"Private message from {sender} -> {recipient}: {status}",
        "Value": message,
    })

  def send_messages(
      self,
      agent: str,
      proposed_action: str,
  ) -> list[dict[str, Any]]:
    """Send messages from agent, called in run_simulation()."""
    processed_messages = []
    try:
      proposed_json = extract_json(proposed_action)
    except ValueError as error:
      outcome = f"Communication attempt for {agent} rejected: {error}"
      raise ValueError(outcome)
    else:
      messages = proposed_json.get("private_messages")
      if not isinstance(messages, list):
        raise ValueError(f"Communication attempt for {agent} rejected: private_messages is not a valid list.")

      week = self._calendar.get_week()
      phase = self._calendar.get_phase()

      if phase != "communication":
        raise ValueError(f"Communication attempt for {agent} rejected: current phase is communication.")

      if messages != []:
        for message in messages:
          recipient = None
          content = None
          status = "succeeded"
          failure_type = None
          if not isinstance(message, dict):
            status = "rejected"
            failure_type = "invalid_message"
          else:
            recipient = message.get("recipient")
            content = message.get("message")
            if recipient == None or recipient not in self._agents or recipient == agent:
              status = "rejected"
              failure_type = "invalid_recipient"
            elif not isinstance(content, str) or content == "":
              status = "rejected"
              failure_type = "invalid_message_content"
            elif len(content.split()) > self._max_words:
              status = "rejected"
              failure_type = "invalid_message_length"

          # Record each message, invalid ones as well.
          self.record_event(
            week=week,
            sender=agent,
            recipient=recipient,
            content=content,
            status=status,
            failure_type=failure_type,
          )

        for message in self._state["messages"][-len(messages):]:
          processed_messages.append(message)
    return copy.deepcopy(processed_messages)

  def get_messages(
      self,
      agent: str,
  ) -> list[dict[str, Any]]:
    """Get all messages of an agent."""
    sent_messages = []
    received_messages = []
    for message in self._state["messages"]:
      if agent == message["sender"]:
        sent_messages.append(message)
      elif agent == message["recipient"] and message["status"] == "succeeded":
        received_messages.append(message)
    messages = {
      "sent_messages": sent_messages,
      "received_messages": received_messages,
    }
    return copy.deepcopy(messages)

  def get_state(self) -> entity_component.ComponentState:
    return {"state": copy.deepcopy(self._state)}

  def set_state(
      self,
      state: entity_component.ComponentState,
  ) -> None:
    self._state = copy.deepcopy(cast(dict[str, Any], state["state"]))
