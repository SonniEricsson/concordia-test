
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

    # Last event_id an agent used as evidence for a relationship update.
    last_reflection_id = {}
    for agent in agents:
      last_reflection_id[agent] = 0

    self._state: dict[str, Any] = {
      "departments": departments,
      "agents": agents,
      "next_reflection_id": 1,
      "history": list(history or []),
      "personal_relationships": personal_relationships,
      "department_relationships": department_relationships,
      "last_reflection_id": last_reflection_id,
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
      dimensions: PersonalDimensionScores,
      reasoning: str,
      week: int,
  ) -> dict[str, Any]:
    """Update personal relationship from agent."""
    if self.check_personal_pair(agent, target):
      relationship = self._state["personal_relationships"][agent][target]
      previous_scores = dict(relationship)
      #if delta:
      #  for dimension, update_value in dimensions.items():
      #    new_value = relationship[dimension] + update_value
      #    relationship[dimension] = max(MIN_SCORE, min(MAX_SCORE, new_value))
      for dimension, update_value in dimensions.items():
        relationship[dimension] = max(MIN_SCORE, min(MAX_SCORE, update_value))

      self._state["personal_relationships"][agent][target] = relationship

      outcome = f"Relationship between {agent} and {target} has been updated."
      status = "succeeded"
      return self.record_event(
          entity_a=agent,
          entity_b=target,
          relationship_type="personal",
          update=dict(relationship),
          previous_scores=previous_scores,
          reasoning=reasoning,
          week=week,
          outcome=outcome,
          status=status,
      )
    else:
      outcome = f"{agent} does not have a valid relationship with {target}."
      status = "rejected"
      failure_type = "invalid_target"
      return self.record_event(
          entity_a=agent,
          entity_b=target,
          relationship_type="personal",
          update=dimensions,
          reasoning=reasoning,
          week=week,
          outcome=outcome,
          status=status,
          failure_type=failure_type,
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
          week=week,
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
          week=week,
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
    last_reflection_id = self._state["last_reflection_id"].get(agent)
    recent_events = []
    # Evidence consists of university events.
    for event in evidence:
      if event.get("event_id") > last_reflection_id:
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
    current_week = self._calendar.get_week()
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
        week=current_week,
        update=invalid_proposed_json,
        outcome=outcome,
        status="rejected",
        failure_type="invalid_json"
      )
    else:
      if proposed_json.get("action") != "update_relationship":
        outcome = f"{agent} did not choose update_relationship as an action."
        self.record_event(
          entity_a=agent,
          week=current_week,
          update=proposed_json,
          outcome=outcome,
          status="rejected",
          failure_type="invalid_action"
        )
      else:
        # Apply relationship update if update is valid.
        self.apply_update(agent, proposed_json, current_week, recent_events)

    return copy.deepcopy(self._state["history"][history_length:])

  def apply_update(
      self,
      agent: str,
      proposed_json: dict[str, Any],
      week: int,
      recent_events: dict[str, dict[str, Any]],
  ) -> None:
    """Apply relationship updates of agent."""
    # Agent can update relationship with multiple colleagues.
    updates = proposed_json.get("updates")
    if not isinstance(updates, list):
      outcome = f"{agent} provided an invalid relationship updates list."
      status = "rejected"
      failure_type = "invalid_relationship_list"
      self.record_event(
        entity_a=agent,
        update=[],
        week=week,
        outcome=outcome,
        status=status,
        failure_type=failure_type,
      )

    elif updates != []:
      valid_updates = []
      for update in updates:
        valid_update = True

        if not isinstance(update, dict) or update == {}:
          outcome = f"{agent} provided an update with an invalid structure."
          status = "rejected"
          failure_type = "invalid_update"
          valid_update = False
        else:
          target = update.get("target")
          scores = update.get("scores")
          #delta = update.get("delta")
          evidence_ids = update.get("evidence_ids")
          reasoning = update.get("reasoning")

          if isinstance(target, str):
            relationship = self._state["personal_relationships"][agent].get(target)
            if relationship != None:
              relationship = dict(relationship)
          else:
            relationship = None

          if not isinstance(scores, dict) or set(scores) != set(PERSONAL_DIMENSIONS):
            outcome = f"{agent} provided update scores that don't match existing dimensions."
            status = "rejected"
            failure_type = "invalid_scores"
            valid_update = False
          elif not isinstance(target, str) or target not in self._state["agents"]:
            outcome = f"{agent} tried to update the relationship with a target that doesn't exist: {target}"
            status = "rejected"
            failure_type = "invalid_target"
            valid_update = False
          elif target == agent:
            outcome = f"{agent} tried to update the relationship with themself as the target."
            status = "rejected"
            failure_type = "invalid_target"
            valid_update = False
          elif not isinstance(reasoning, str) or reasoning == "":
            outcome = f"{agent} did not provide a valid reasoning for the relationship update."
            status = "rejected"
            failure_type = "invalid_reasoning"
            valid_update = False
          elif not isinstance(evidence_ids, list) or evidence_ids == []:
            outcome = f"{agent} did not provide a valid evidence list for the relationship update."
            status = "rejected"
            failure_type = "invalid_evidence"
            valid_update = False
          else:
            for id in evidence_ids:
              if id not in recent_events:
                outcome = f"{agent} provided evidence {id} for the relationship update, but it is not a recent event."
                status = "rejected"
                failure_type = "invalid_evidence_id"
                valid_update = False
              elif recent_events[id].get("agent") != target:
                outcome = f"{agent} provided evidence {id} for the relationship update, but it is not describing an action of {target}."
                status = "rejected"
                failure_type = "invalid_evidence"
                valid_update = False
            for dimension, score in scores.items():
              if not isinstance(score, int):
                outcome = f"{agent} provided relationship scores that are not integers."
                status = "rejected"
                failure_type = "invalid_scores"
                valid_update = False

        # Collect valid updates in a list.
        if valid_update:
          valid_updates.append((target, scores, evidence_ids, reasoning))

        else:
          # Record invalid updates.
          self.record_event(
            entity_a=agent,
            entity_b=target,
            relationship_type="personal",
            update=scores,
            previous_scores=relationship,
            reasoning=reasoning,
            week=week,
            outcome=outcome,
            status=status,
            failure_type=failure_type,
          )

      #if len(valid_updates) == len(updates):
      # Update valid relationships, even if some updates are invalid (don't reject whole batch).
      for target, scores, evidence_ids, reasoning in valid_updates:
        evidence = []
        for id in evidence_ids:
          evidence.append(f"Event {id}: {recent_events[id].get("outcome")}")
        full_reasoning = reasoning + "\nEvents as evidence:\n" + "\n".join(evidence)

        self.update_personal_relationship(
            agent=agent,
            target=target,
            dimensions=scores,
            reasoning=full_reasoning,
            week=week,
        )

      if recent_events != {}:
        # Save the last referenced university event id.
        self._state["last_reflection_id"][agent] = max(
          max(recent_events.keys()),
          self._state["last_reflection_id"].get(agent),
        )

    else:
      outcome = f"No relationship changes for {agent}."
      status = "succeeded"
      self.record_event(
        entity_a=agent,
        updates=[],
        week=week,
        outcome=outcome,
        status=status,
      )

      #if recent_events != {}:
      #  self._state["last_reflection_id"][agent] = max(
      #    max(recent_events.keys()),
      #    self._state["last_reflection_id"].get(agent),
      #  )

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
    entity_b: str | None = None,
    relationship_type: str | None = None,
    update: dict[str, int] | None = None,
    previous_scores: dict[str, int] | None = None,
    reasoning: str | None = None,
    week: int,
    outcome: str,
    status: STATUS_OPTIONS,
    failure_type: str | None = None,
  ) -> dict[str, Any]:
    """Record event and add it to the state history."""
    event = {
        "reflection_id": len(self._state["history"]) + 1,
        "reflection_type": "relationship_update",
        #"step": None,
        "week": week,
        "phase": self._calendar.get_phase(),
        "relationship_type": relationship_type,
        "entity_a": entity_a,
        "entity_b": entity_b,
        "update": update,
        "previous_scores": previous_scores,
        "reasoning": reasoning,
        "outcome": outcome,
        "status": status,
        "failure_type": failure_type,
    }

    self._state["next_reflection_id"] += 1
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
