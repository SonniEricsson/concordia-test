import json
from typing import cast, Any, Literal

from concordia.typing import entity_component
from university.components.academic_calendar import AcademicCalendar

CATEGORIES = {"personal", "relationship", "other"}
MAX_TITLE_LENGTH = 30
MAX_NOTE_LENGTH = 300
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

class PersonalNotebook(
    entity_component.ContextComponent,
    entity_component.ComponentWithLogging,
):
  """A component that stores personal notes from agents."""

  def __init__(
      self,
      *,
      agents: list[str],
      calendar: AcademicCalendar,
      pre_act_label: str = "\nPersonal notebook"
  ):
    super().__init__()
    self._pre_act_label = pre_act_label
    self._agents = agents
    self._calendar = calendar
    notebook = {}
    personal_notes = {}
    relationship_notes = {}
    other_notes = {}
    archive = {}
    for agent in self._agents:
      notebook[agent] = {}
      personal_notes[agent] = {}
      relationship_notes[agent] = {}
      other_notes[agent] = {}
      archive[agent] = {}
    self._state = {
      "notebook": notebook,
      "personal_notes": personal_notes,
      "relationship_notes": relationship_notes,
      "other_notes": other_notes,
      "history": [],
      "archive": archive,
      "next_note_id": 1,
      "next_event_id": 1,
    }

  def record_event(
      self,
      *,
      agent: str,
      proposal: dict[str, Any],
      old_note: dict[str, Any] | None = None,
      new_note: dict[str, Any] | None = None,
      outcome: str,
      status: STATUS_OPTIONS,
      failure_type: str | None = None,
  ) -> dict[str, Any]:
    """Record event and add it to the state history."""
    week = self._calendar.get_week()
    reflection = {}
    if isinstance(proposal, dict):
      reflection = proposal
    action = reflection.get("action")
    event = {
        "event_id": self._state["next_event_id"],
        "agent": agent,
        "note_id": reflection.get("note_id"),
        "action": action,
        "week": week,
        "old_note": old_note,
        "new_note": new_note,
        "outcome": outcome,
        "status": status,
        "failure_type": failure_type,
    }

    self._state["next_event_id"] += 1
    self._state["history"].append(event)

    self._logging_channel({
        "Key": self._pre_act_label,
        "Summary": f"Reflection note by {agent}: {action}",
        "Value": event,
    })

    return event

  def resolve_reflection(
      self,
      agent: str,
      proposed_reflection: str,
  ) -> list[dict[str, Any]]:
    week = self._calendar.get_week()
    week_id = f"week_{week}"
    history_length = len(self._state["history"])

    try:
      proposed_json = extract_json(proposed_reflection)
    except ValueError as error:
      invalid_proposed_json = {
        "invalid_response": proposed_reflection,
      }
      outcome = f"{agent} generated an invalid response: {error}"
      self.record_event(
        agent=agent,
        proposal=invalid_proposed_json,
        outcome=outcome,
        status="rejected",
        failure_type="invalid_json"
      )
    else:
      reflection_notes = proposed_json.get("reflection_notes")
      if not isinstance(reflection_notes, list) or reflection_notes == []:
        invalid_reflection_notes = {
          "invalid_response": reflection_notes,
        }
        outcome = f"reflection_notes is not a valid list."
        self.record_event(
          agent=agent,
          proposal=invalid_reflection_notes,
          outcome=outcome,
          status="rejected",
          failure_type="invalid_reflection_notes_list"
        )
      else:
        for reflection in reflection_notes:
          self.apply_reflection(agent, reflection)

    return self._state["history"][history_length:]

  def apply_reflection(
      self,
      agent: str,
      reflection: dict[str, Any],
  ) -> None:
    agent_reflections = {
      "create_note": self.create_note,
      "update_note": self.update_note,
      "discard_note": self.discard_note,
    }

    try:
      if not isinstance(reflection, dict) or reflection == {}:
        raise ValueError("Reflection has an invalid structure.")

      action = reflection.get("action")
      if action not in agent_reflections:
        raise ValueError("Action for the reflection is not valid.")

      old_note = None
      if action in ("update_note", "discard_note"):
        note_id = reflection.get("note_id")
        old_note = dict(self._state["notebook"][agent].get(note_id))
        #old_note = self.read_note(agent, reflection.get("note_id"))

      start_reflection = agent_reflections.get(action)
      new_note = start_reflection(agent=agent, reflection=reflection)
    except ValueError as error:
      self.record_event(
        agent=agent,
        proposal=reflection,
        outcome=str(error),
        status="rejected",
        failure_type="invalid_note_action",
      )
    else:
      note_id = new_note.get("note_id")
      outcome = f"Reflection for note {note_id}: {action}"
      self.record_event(
        agent=agent,
        proposal=reflection,
        old_note=old_note,
        new_note=new_note,
        outcome=outcome,
        status="succeeded",
      )

  def check_config(
      self,
      agent: str,
      reflection: dict[str, Any],
  ) -> None:
    category = reflection.get("category")
    if category not in CATEGORIES:
      raise ValueError(f"Category is not a valid string from {CATEGORIES}")

    action = reflection.get("action")
    note_id = reflection.get("note_id")
    title = reflection.get("title")
    if action == "create_note":
      if note_id != None:
        raise ValueError("Note creation does not accept a note_id.")
      if not isinstance(title, str) or title == "" or len(title.split()) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title is not a valid string with less than {MAX_TITLE_LENGTH} words.")

    if action != "create_note" and note_id not in self._state["notebook"][agent]:
      raise ValueError("Referenced note_id does not exist in agent's notebook.")

    content = reflection.get("content")
    if action != "discard_note" and (not isinstance(content, str) or content == "" or len(content.split()) > MAX_NOTE_LENGTH):
      raise ValueError(f"Content is not a valid string with less than {MAX_NOTE_LENGTH} words.")

    target = reflection.get("target")
    if category == "relationship":
      if target not in self._agents or target == agent:
        raise ValueError("Target is not a valid colleague.")
      elif action == "create_note" and self._state["relationship_notes"][agent].get(target) != None:
        raise ValueError("Note for target already exists, update it instead.")
    elif target != None:
      raise ValueError(f"{category} notes cannot have a target.")


  def create_note(
      self,
      *,
      agent: str,
      reflection: dict[str, Any],
  ) -> dict[str, Any]:
    self.check_config(agent, reflection)

    note_id = f"note_{self._state["next_note_id"]}"
    self._state["next_note_id"] += 1
    week = self._calendar.get_week()
    category = reflection.get("category")
    note = {
      "note_id": note_id,
      "category": category,
      "title": reflection.get("title"),
      "content": reflection.get("content"),
      "target": reflection.get("target"),
      "created_week": week,
      "updated_week": week,
      "revision": 1,
    }

    self._state["notebook"][agent][note_id] = note
    self._state[f"{category}_notes"][agent][note_id] = note

    return note

  def update_note(
      self,
      *,
      agent: str,
      reflection: dict[str, Any],
  ) -> dict[str, Any]:
    self.check_config(agent, reflection)
    note_id = reflection.get("note_id")
    note = self._state["notebook"][agent].get(note_id)
    category = reflection.get("category")
    note.update(
      content=reflection.get("content"),
      updated_week=self._calendar.get_week(),
      revision=note["revision"] + 1,
    )

    self._state["notebook"][agent][note_id] = note
    self._state[f"{category}_notes"][agent][note_id] = note

    return note

  def discard_note(
      self,
      *,
      agent: str,
      reflection: dict[str, Any],
  ) -> dict[str, Any]:
    self.check_config(agent, reflection)
    note_id = reflection.get("note_id")
    note = dict(self._state["notebook"][agent].get(note_id))
    category = reflection.get("category")
    note.update(
      updated_week=self._calendar.get_week(),
      revision=note["revision"] + 1,
    )
    self._state["archive"][agent][note_id] = note

    del self._state["notebook"][agent][note_id]
    del self._state[f"{category}_notes"][agent][note_id]

    return note

  def get_notebook(
      self,
      agent: str,
  ) -> dict[str, Any]:
    week = self._calendar.get_week()

    reflections = {}

    for category in CATEGORIES:
      reflections[category] = []
      for note in self._state[f"{category}_notes"][agent].values():
        reflections[category].append(note)
      reflections[category].sort(key=lambda note: note["updated_week"], reverse=True)

    results = {
      "agent": agent,
      "week": week,
      "personal_notes": reflections["personal"],
      "relationship_notes": reflections["relationship"],
      "other_notes": reflections["other"],
    }

    return results

  def get_state(self) -> entity_component.ComponentState:
    return {"state": self._state}

  def set_state(
      self,
      state: entity_component.ComponentState,
  ) -> None:
    self._state = cast(dict[str, Any], state["state"])
