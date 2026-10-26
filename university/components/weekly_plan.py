import copy
import json
from typing import Any, cast, Literal
from concordia.typing import entity_component
from university.components.academic_calendar import AcademicCalendar

DEFAULT_MAX_PLAN_WORDS = 150
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

class WeeklyPlan(
    entity_component.ContextComponent,
    entity_component.ComponentWithLogging,
):
  """A component that represents the weekly plans of university agents during planning phase."""
  def __init__(
      self,
      *,
      calendar: AcademicCalendar,
      pre_act_label: str = "\nWeekly plans"
  ):
    super().__init__()
    self._pre_act_label = pre_act_label
    self._calendar = calendar
    self._state = {
      "plans": {"week1": {}},
      "history": [],
    }

  def resolve_action(
      self,
      agent: str,
      proposed_action: str,
  ) -> dict[str, str]:
    """Resolve a proposed action from an agent and set their weekly plan, called during run_simulation()."""
    week = self._calendar.get_week()
    status = "succeeded"
    failure_type = None
    week_id = f"week{week}"
    # Check if dict for current week has been created yet.
    if self._state["plans"].get(week_id) == None:
      self._state["plans"][week_id] = {}

    try:
      proposed_json = extract_json(proposed_action)
    except ValueError as error:
      plan = str(error)
      status = "rejected"
      failure_type = "invalid_json"
    else:
      plan = proposed_json.get("weekly_plan")
      if (
        not isinstance(plan, str)
        or len(plan.split()) > DEFAULT_MAX_PLAN_WORDS
        or plan == ""
      ):
        plan = f"Weekly plan {week} is not a valid string with less that {DEFAULT_MAX_PLAN_WORDS} words."
        status = "rejected"
        failure_type = "invalid_plan"

    # Set the weekly plan.
    self.set_plan(agent, plan, status, failure_type)

    current_plan = self.get_plan(agent)

    return current_plan


  def set_plan(
      self,
      agent: str,
      plan: str,
      status: STATUS_OPTIONS,
      failure_type: str | None = None,
  ) -> None:
    """Set the weekly plan of the agent."""
    week = self._calendar.get_week()
    week_id = f"week{week}"

    self._state["plans"][week_id][agent] = {
      "plan": plan,
      "status": status,
      "failure_type": failure_type,
    }

    weekly_plan = {
      "agent": agent,
      "week": week,
      "plan": plan,
      "status": status,
      "failure_type": failure_type,
    }

    self._state["history"].append(weekly_plan)

    self._logging_channel({
        "Key": self._pre_act_label,
        "Summary": f"Weekly plan for {agent}, week {week}: {status}",
        "Value": weekly_plan,
    })

  def get_plan(
      self,
      agent: str,
  ) -> dict[str, str]:
    """Get the plan of the current week."""
    week = self._calendar.get_week()
    plan = self._state["plans"].get(f"week{week}", {}).get(agent)
    current_plan = {
      "agent": agent,
      "week": week,
      "plan": None,
      "status": None,
      "failure_type": None,
    }
    if plan != None:
      current_plan.update(plan)

    return current_plan

  def get_state(self) -> entity_component.ComponentState:
    return {"state": copy.deepcopy(self._state)}

  def set_state(
      self,
      state: entity_component.ComponentState,
  ) -> None:
    self._state = copy.deepcopy(cast(dict[str, Any], state["state"]))
