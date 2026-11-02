
import json
import copy
from concordia.typing import entity_component
from concordia.typing import entity as entity_lib
from typing import Any, cast, Literal
from university.components.academic_calendar import AcademicCalendar


PERSONAL_DIMENSIONS = (
  "trust",
  "respect",
)

DEPARTMENT_DIMENSIONS = (
  "cooperation",
  "competition"
)

STATUS_OPTIONS = Literal["succeeded", "rejected"]

MIN_SCORE = -10
MAX_SCORE = 10

PersonalDimensionScores = dict[str, int] # PERSONAL_DIMENSIONS
DepartmentDimensionScores = dict[str, int] # DEPARTMENT_DIMENSIONS

PersonalScores = dict[str, dict[str, PersonalDimensionScores]] # {person: {target: scores}}
DepartmentScores = dict[str, dict[str, DepartmentDimensionScores]] # {department: {target: scores}}

def extract_json(text: str) -> dict[str, Any]:
  """Extract the JSON object from a generated response."""
  try:
    content = json.loads(text)
  except json.JSONDecodeError as error:
    raise ValueError(f"Invalid JSON: {error}")

  if not isinstance(content, dict):
    raise ValueError("The action is not a JSON object.")

  return content

def neutral_personal_scores() -> PersonalDimensionScores:
  neutral_scores = {}
  for dimension in PERSONAL_DIMENSIONS:
    neutral_scores[dimension] = 0

  return neutral_scores

def neutral_department_scores() -> DepartmentDimensionScores:
  neutral_scores = {}
  for dimension in DEPARTMENT_DIMENSIONS:
    neutral_scores[dimension] = 0

  return neutral_scores

class RelationshipState(
    entity_component.ContextComponent,
    entity_component.ComponentWithLogging,
):
  """A component that represents the relationships between university agents for the reflection phase."""

  def __init__(
      self,
      *,
      agents: list[str],
      departments: list[str],
      calendar: AcademicCalendar,
      pre_act_label: str = "\nRelationships",
      initial_personal_relationships: (dict[str, dict[str, PersonalDimensionScores]] | None) = None,
      initial_department_relationships: (dict[str, dict[str, DepartmentDimensionScores]] | None) = None,
      history: list[dict[str, Any]] | None = None,
  ):
    super().__init__()
    self._pre_act_label = pre_act_label
    self._calendar = calendar

    # Neutral scores.
    # Relationships are two-directional.
    personal_relationships = self.create_personal_scores(agents)
    department_relationships = self.create_department_scores(departments)

    self._state: dict[str, Any] = {
      "departments": departments,
      "agents": agents,
      "next_update_id": 1,
      "history": list(history or []),
      "personal_relationships": personal_relationships,
      "department_relationships": department_relationships,
      #"last_reflection_id": last_reflection_id,
    }

    self.set_personal_relationships(initial_personal_relationships or {})
    self.set_department_relationships(initial_department_relationships or {})


  @staticmethod
  def create_personal_scores(
      agents: list[str],
  ) -> PersonalScores:
    """Initialize neutral scores for all personal relationships."""
    scores = {}
    for person in agents:
      person_scores = {}
      for target in agents:
        if person != target:
          person_scores[target] = neutral_personal_scores()
      scores[person] = person_scores
    return scores

  @staticmethod
  def create_department_scores(
      departments: list[str],
  ) -> DepartmentScores:
    """Initialize neutral scores for all department relationships."""
    scores = {}
    for department in departments:
      department_scores = {}
      for target in departments:
        if department != target:
          department_scores[target] = neutral_department_scores()
      scores[department] = department_scores
    return scores

  def check_personal_pair(
      self,
      person_a: str,
      person_b: str,
  ) -> bool:
    """Check if relationship is possible."""
    if person_a not in self._state["agents"]:
      return False
    elif person_b not in self._state["agents"]:
      return False
    elif person_a == person_b:
      return False
    else:
      return True


  def check_department_pair(
      self,
      department_a: str,
      department_b: str,
  ) -> bool:
    """Check if relationship is possible."""
    if department_a not in self._state["departments"]:
      return False
    elif department_b not in self._state["departments"]:
      return False
    elif department_a == department_b:
      return False
    else:
      return True

  def set_personal_relationships(
      self,
      initial_relationships: dict[str, dict[str, PersonalDimensionScores]],
  ) -> None:
    """Update all personal relationships with given setting."""
    for person_a, relationships in initial_relationships.items():
      for person_b, scores in relationships.items():
        if self.check_personal_pair(person_a, person_b):
          for dimension, value in scores.items():
            self._state["personal_relationships"][person_a][person_b][dimension] = max(MIN_SCORE, min(MAX_SCORE, value))

  def set_department_relationships(
      self,
      initial_relationships: dict[str, dict[str, DepartmentDimensionScores]],
  ) -> None:
    """Update all department relationships with given setting."""
    for department_a, relationships in initial_relationships.items():
      for department_b, scores in relationships.items():
        if self.check_department_pair(department_a, department_b):
          for dimension, value in scores.items():
            self._state["department_relationships"][department_a][department_b][dimension] = max(MIN_SCORE, min(MAX_SCORE, value))

  def update_personal_relationship(
      self,
      agent: str,
      target: str,
      update: dict[str, Any],
      reasoning: str,
  ) -> None:
    scores = update.get("scores")
    if not isinstance(scores, dict) or set(scores) != set(PERSONAL_DIMENSIONS):
      raise ValueError("Relationship update scores don't match existing dimensions.")

    for score in scores.values():
      if type(score) is not int or not MIN_SCORE <= score <= MAX_SCORE:
        raise ValueError("Provided scores for relationship update are not valid integers.")

    """Update personal relationship from agent."""
    relationship = self._state["personal_relationships"][agent][target]
    old_scores = dict(relationship)

    for dimension, update_value in scores.items():
      relationship[dimension] = update_value

    self._state["personal_relationships"][agent][target] = relationship

    self.record_event(
      entity_a=agent,
      update=update,
      old_scores=old_scores,
      outcome=f"Relationship between {agent} and {target} has been updated.",
      reasoning=reasoning,
      status="succeeded",
    )

  def update_department_relationship(
      self,
      department_a: str,
      department_b: str,
      dimensions: DepartmentDimensionScores,
      reasoning: str,
      week: int,
  ) -> dict[str, Any]:
    """Update department relationship."""
    if self.check_department_pair(department_a, department_b):
      relationship = self._state["department_relationships"][department_a][department_b]
      previous_scores = dict(relationship)
      #if delta:
      #  for dimension, update_value in dimensions.items():
      #    new_value = relationship[dimension] + update_value
      #    relationship[dimension] = max(MIN_SCORE, min(MAX_SCORE, new_value))
      #else:
      for dimension, update_value in dimensions.items():
        relationship[dimension] = max(MIN_SCORE, min(MAX_SCORE, update_value))

      self._state["department_relationships"][department_a][department_b] = relationship

      outcome = f"Relationship between {department_a} and {department_b} has been updated."
      status = "succeeded"
      return self.record_event(
          entity_a=department_a,
          entity_b=department_b,
          relationship_type="department",
          update=dict(relationship),
          previous_scores=previous_scores,
          reasoning=reasoning,
          outcome=outcome,
          status=status,
      )
    else:
      outcome = f"{department_a} does not have a valid relationship with {department_b}."
      status = "rejected"
      failure_type = "invalid_target"
      return self.record_event(
          entity_a=department_a,
          entity_b=department_b,
          relationship_type="department",
          update=dimensions,
          reasoning=reasoning,
          outcome=outcome,
          status=status,
          failure_type=failure_type,
      )

  def get_reflection_state(
      self,
      agent: str,
      evidence: list[dict[str, Any]],
  ) -> dict[str, Any]:
    """Get relationships and recent events since the last reflection of an agent."""
    #last_reflection_id = self._state["last_reflection_id"].get(agent)
    recent_events = []
    week = self._calendar.get_week()
    # Evidence consists of university events.
    for event in evidence:
      #if event.get("event_id") > last_reflection_id:
      if event["week"] == week:
        recent_events.append(event)
    reflection_state = {
      "reflection_agent": agent,
      "current_relationships": copy.deepcopy(self._state["personal_relationships"].get(agent)),
      "recent_events": copy.deepcopy(recent_events),
    }

    return reflection_state

  def resolve_update(
      self,
      agent: str,
      proposed_action: str,
      evidence: list[dict[str, Any]],
  ) -> list[dict[str, Any]]:
    """Resolve a proposed action from an agent and apply relationship updates, called during run_simulation()."""
    week = self._calendar.get_week()
    history_length = len(self._state["history"])
    reflection_state = self.get_reflection_state(agent, evidence)
    recent_events = {}
    for event in reflection_state["recent_events"]:
      recent_events[event["event_id"]] = event

    try:
      proposed_json = extract_json(proposed_action)
    except ValueError as error:
      invalid_proposed_json = {
        "invalid_update": proposed_action,
      }
      outcome = f"{agent} generated an invalid relationship update: {error}"
      self.record_event(
        entity_a=agent,
        update=invalid_proposed_json,
        outcome=outcome,
        status="rejected",
        failure_type="invalid_json",
      )
    else:
      # Agent can update relationship with multiple colleagues.
      relationship_updates = proposed_json.get("relationship_updates")
      if not isinstance(relationship_updates, list):
        invalid_relationship_updates = {
          "invalid_response": relationship_updates,
        }
        outcome = f"relationship_updates is not a valid list."
        self.record_event(
          entity_a=agent,
          update=invalid_relationship_updates,
          outcome=outcome,
          status="rejected",
          failure_type="invalid_relationship_updates_list",
        )
      elif relationship_updates == []:
        outcome = f"No relationship changes for {agent}."
        status = "succeeded"
        self.record_event(
          entity_a=agent,
          update=[],
          outcome=outcome,
          status=status,
        )
      else:
        for update in relationship_updates:
          # Apply relationship update if update is valid.
          self.apply_update(agent, update, recent_events)

    return copy.deepcopy(self._state["history"][history_length:])

  def apply_update(
      self,
      agent: str,
      update: dict[str, Any],
      recent_events: dict[str, dict[str, Any]],
  ) -> None:
    """Apply relationship updates of agent."""
    try:
      if not isinstance(update, dict) or update == {}:
        raise ValueError("Relationship update has an invalid structure.")

      target = update.get("target")
      if not self.check_personal_pair(agent, target):
        raise ValueError("Target for relationship update is not valid.")

      evidence_ids = update.get("evidence_ids")
      if not isinstance(evidence_ids, list) or evidence_ids == []:
        raise ValueError("Evidence list for relationship update is not a valid list.")

      reasoning = update.get("reasoning")
      if not isinstance(reasoning, str) or reasoning == "":
        raise ValueError("Reasoning for relationship update is not a valid string.")

      for id in evidence_ids:
        if id not in recent_events:
          raise ValueError("Provided evidence_id for relationship update is not a recent event.")
        if recent_events[id].get("agent") != target:
          raise ValueError("Provided evidence_id for relationship update is not describing an action of the target.")

      evidence = []
      for id in evidence_ids:
        evidence.append(f"Event {id}: {recent_events[id].get("outcome")}")
      full_reasoning = reasoning + "\nEvents as evidence:\n" + "\n".join(evidence)

      self.update_personal_relationship(agent, target, update, full_reasoning)

    except ValueError as error:
      self.record_event(
        entity_a=agent,
        update=update,
        relationship_type="personal",
        outcome=str(error),
        status="rejected",
        failure_type="invalid_relationship_update",
      )

  # Assign current step to each event.
  #def assign_step(
  #    self,
  #    step: int,
  #) -> None:
  #  for event in reversed(self._state["history"]):
  #    if event.get("step") is None:
  #      event["step"] = step
  #    else:
  #      break

  def record_event(
    self,
    *,
    entity_a: str,
    update: dict[str, Any],
    old_scores: dict[str, int] | None = None,
    outcome: str,
    reasoning: str | None = None,
    status: STATUS_OPTIONS,
    failure_type: str | None = None,
  ) -> dict[str, Any]:
    """Record event and add it to the state history."""
    entity_b = update.get("target")
    new_scores = update.get("scores")
    relationship_type = "personal"
    if reasoning == None:
      reasoning = update.get("reasoning")
    week = self._calendar.get_week()
    event = {
        "update_id": len(self._state["history"]) + 1,
        "reflection_type": "relationship_update",
        #"step": None,
        "week": week,
        "relationship_type": relationship_type,
        "entity_a": entity_a,
        "entity_b": entity_b,
        "new_scores": new_scores,
        "old_scores": old_scores,
        "reasoning": reasoning,
        "outcome": outcome,
        "status": status,
        "failure_type": failure_type,
    }

    self._state["next_update_id"] += 1
    self._state["history"].append(event)

    self._logging_channel({
        "Key": self._pre_act_label,
        "Summary": (
            f"Relationship update {entity_a} -> {entity_b}: {update} because {reasoning}"
        ),
        "Value": event,
    })

    return event

  def get_pre_act_label(self) -> str:
    return self._pre_act_label

  def get_pre_act_value(self) -> str:
    """Return the current state of all relationships."""
    personal_relationships = {}

    for person_a, relationships in self._state["personal_relationships"].items():
      for person_b, scores in relationships.items():
        personal_relationships[f"{person_a} -> {person_b}"] = scores

    department_relationships = {}

    for department_a, relationships in self._state["department_relationships"].items():
      for department_b, scores in relationships.items():
        department_relationships[f"{department_a} -> {department_b}"] = scores

    relationships_context = {
      "personal_relationships": personal_relationships,
      "department_relationships": department_relationships,
    }

    return json.dumps(relationships_context, indent=2)

  def pre_act(
      self,
      action_spec: entity_lib.ActionSpec,
  ) -> str:
    result = self.get_pre_act_value()
    self._logging_channel({
        'Key': self._pre_act_label,
        'Summary': result,
        'Value': result,
    })
    return result

  def get_state(self) -> entity_component.ComponentState:
    return {"state": copy.deepcopy(self._state)}

  def set_state(
      self,
      state: entity_component.ComponentState,
  ) -> None:
    self._state = cast(dict[str, Any], state["state"])
