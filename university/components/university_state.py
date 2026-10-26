import json
import copy
from typing import Any, cast, Literal

from concordia.typing import entity as entity_lib
from concordia.typing import entity_component
from university.components.academic_calendar import AcademicCalendar

STATUS_OPTIONS = Literal["succeeded", "rejected", "no_action"]
BUDGET_APPROVERS = ["Department Chair", "Budget Officer"]

def extract_json(text: str) -> dict[str, Any]:
  """Extract the JSON object from a generated response."""
  try:
    content = json.loads(text)
  except json.JSONDecodeError as error:
    raise ValueError(f"Invalid JSON: {error}")

  if not isinstance(content, dict):
    raise ValueError("The action is not a JSON object.")

  return content

# Similarily to components\game_master\world_state.py.
class UniversityState(
    entity_component.ContextComponent,
    entity_component.ComponentWithLogging,
):
  """A component that represents the authoritative state of the university simulation."""
  def __init__(
      self,
      *,
      agents: list[str],
      organization: str,
      departments: list[str],
      budget: int,
      tasks: dict[str, dict[str, Any]],
      rules: list[str],
      pre_act_label: str = "\nUniversity state",
      agent_roles: dict[str, str],
      calendar: AcademicCalendar,
  ):
    super().__init__()
    self._pre_act_label = pre_act_label
    self._agent_roles = dict(agent_roles)
    self._calendar = calendar

    events = []
    rewards = {}
    for agent in agents:
      rewards[agent] = 0

    week = calendar.get_week()

    current_tasks = {}
    task_ids = []
    for task_id, task in tasks.items():
      current_tasks[task_id] = dict(task)
      task_ids.append(task_id)

    # Keeps track on how often an agent has worked on a task in which week.
    worked_on_task = {}
    for agent in agents:
      worked_on_task[agent] = {}

    self._state: dict[str, Any] = {
      "organization": organization,
      "departments": departments,
      "agents": agents,
      "agent_roles": agent_roles,
      "week": week,
      #"turn": 0,
      "budget": budget,
      "budget_spent": 0,
      "tasks": current_tasks,
      "task_ids": task_ids,
      "worked_on_task": worked_on_task,
      "rules": list(rules),
      "last_action": None,
      "next_event_id": 1,
      "last_outcome": "",
      "events": events,
      "rewards": rewards,
    }

  def get_pre_act_label(self) -> str:
    return self._pre_act_label

  def get_pre_act_value(self) -> str:
    """Returns the current university state."""
    self._state["week"] = self._calendar.get_week()
    result = '\n'.join([
        f'{name}: {value}' for name, value in self._state.items()
    ])
    return result + '\n'

  def pre_act(
      self,
      action_spec: entity_lib.ActionSpec,
  ) -> str:
    result = self.get_pre_act_value()
    self._logging_channel({
        "Key": self._pre_act_label,
        "Summary": result,
        "Value": result,
    })
    return result

  # Action should be resolved during event resolution instead of post_act.
  # Then the resolved outcome can be propagated to the agents.
  def resolve_action(
      self,
      agent: str,
      proposed_action: str,
  ) -> dict[str, Any]:
    """Resolve a proposed action from an agent and apply university action, called during run_simulation()."""
    current_week = self._calendar.get_week()

    try:
      proposed_json = extract_json(proposed_action)
    except ValueError as error:
      invalid_proposed_json = {
        "invalid_response": proposed_action,
      }
      outcome = f"{agent} generated an invalid response: {error}"
      self.record_event(
        agent,
        current_week,
        invalid_proposed_json,
        outcome,
        status="rejected",
        failure_type="invalid_json"
      )
    else:
      action = str(proposed_json.get("action"))

      if action == "no_action":
        available_actions = self.get_action_options(agent)
        outcome = f"{agent} chose no action."
        if available_actions != {}:
          outcome = f"{agent} chose no action, but actions are currently available for tasks."
          #for task_id, action in available_actions.items():
        self.record_event(
          agent,
          current_week,
          proposed_json,
          outcome,
          reasoning=str(proposed_json.get("reasoning")),
          status="no_action",
        )
      else:
        self.apply_action(proposed_json, agent, current_week)
        self._state["last_action"] = proposed_json

    return copy.deepcopy(self._state["events"][-1])

  def apply_action(
      self,
      proposed_json: dict[str, Any],
      agent: str,
      week: int,
  ) -> None:
    """Apply university action of agent."""
    agent_actions = {
      "claim_task": self.claim_task,
      "work_on_task": self.work_on_task,
      "approve_budget": self.approve_budget,
    }
    task_id = proposed_json.get("task_id")
    task = self._state["tasks"].get(task_id)
    action = proposed_json.get("action")
    reasoning = proposed_json.get("reasoning")

    valid_action = True

    if action in agent_actions:
      if self.get_action_options(agent).get(task_id) != action:
        outcome = f"Unavailable action: {action} for {task_id} is not included in the available action options."
        status = "rejected"
        failure_type = "unavailable_action"
        valid_action = False

    if action == "create_task":
      self.create_task(agent, week, proposed_json)
      return
    elif action not in agent_actions:
      outcome = f"Unknown action: {action}"
      status = "rejected"
      failure_type = "unknown_action"
      valid_action = False
    elif task is None:
      outcome = f"Unknown task_id: {task_id}, task could not be found."
      status = "rejected"
      failure_type = "unknown_task"
      valid_action = False
    elif not isinstance(reasoning, str) or reasoning == "":
      outcome = f"Invalid or empty reasoning: {reasoning}"
      status = "rejected"
      failure_type = "invalid_reasoning"
      valid_action = False
    elif task.get("change_state") == False:
      outcome = f"{task_id} is rejected. It does not permit state changes."
      status = "rejected"
      failure_type = "change_state_false"
      valid_action = False

    if valid_action:
      start_task = agent_actions.get(action)
      # Execute university action.
      start_task(agent, week, proposed_json)
    else:
      # Record invalid proposals.
      self.record_event(
        agent,
        week,
        proposed_json,
        outcome,
        reasoning=reasoning,
        status=status,
        failure_type=failure_type,
      )

  # Assign current step to each event.
  #def assign_step(
  #    self,
  #    step: int,
  #) -> None:
  #  for event in reversed(self._state["events"]):
  #    if event.get("step") is None:
  #      event["step"] = step
  #    else:
  #      break

  def record_event(
      self,
      agent: str,
      week: int,
      proposal: dict[str, Any],
      outcome: str,
      *,
      reasoning: str | None = None,
      status: STATUS_OPTIONS,
      failure_type: str | None = None,
  ) -> None:
    """Record event and add it to the state event history."""
    task_id = None
    action = proposal.get("action")
    if action == "create_task":
      task_id = self._state["task_ids"][-1]
    elif action != "no_action":
      task_id = proposal.get("task_id")
    event = {
      "event_id": self._state["next_event_id"],
      "event_type": "university_action",
      #"step": None,
      "agent": agent,
      "week": week,
      "phase": self._calendar.get_phase(),
      "action": action,
      "task_id": task_id,
      "reasoning": reasoning,
      "outcome": outcome,
      "reasoning": proposal.get("reasoning"),
      "status": status,
      "failure_type": failure_type,
    }

    self._state["next_event_id"] += 1
    self._state["events"].append(event)
    self._state["last_outcome"] = outcome

    self._logging_channel({
        "Key": self._pre_act_label,
        "Summary": (
            f"University action by {agent}: {action} because {reasoning}"
        ),
        "Value": event,
    })

  def create_task(
      self,
      agent: str,
      week: int,
      proposed_action: dict[str, Any],
  ) -> None:
    """Create a task with generated JSON from agent."""
    if self._state["task_ids"] != []:
      last_task_id = self._state["task_ids"][-1]
      new_task_id = f"task{int(last_task_id[-1]) + 1}"
    else:
      new_task_id = "task1"

    reasoning = str(proposed_action.get("reasoning"))

    task_requirements = [
      "title",
      "task_type",
      "description",
      "department",
      "effort",
      "reward",
      "allowed_roles",
      "change_state",
    ]

    for requirement in task_requirements:
      if proposed_action.get(requirement) == None:
        outcome = f"Task creation for {new_task_id} rejected: {requirement} is missing."
        self.record_event(
            agent,
            week,
            proposed_action,
            outcome,
            reasoning=reasoning,
            status="rejected",
            failure_type=f"task_{requirement}_missing",
        )
        return

    task_type = proposed_action.get("task_type")
    # Personal tasks can only be worked on by the agent who created it, while organizational tasks can be claimed by other agents.
    if task_type not in ("personal", "organizational"):
      outcome = f"Task creation for {new_task_id} rejected: task_type must be personal or organizational."
      self.record_event(
          agent,
          week,
          proposed_action,
          outcome,
          reasoning=reasoning,
          status="rejected",
          failure_type="task_invalid_type",
      )
      return

    effort = proposed_action.get("effort")
    if not 1 <= effort <= 10:
      outcome = f"Task creation for {new_task_id} rejected: effort has to be 1-10."
      self.record_event(
          agent,
          week,
          proposed_action,
          outcome,
          reasoning=reasoning,
          status="rejected",
          failure_type="task_invalid_effort",
      )
      return

    reward = proposed_action.get("reward")
    if not 1 <= reward <= 10:
      outcome = f"Task creation for {new_task_id} rejected: reward has to be 1-10."
      self.record_event(
          agent,
          week,
          proposed_action,
          outcome,
          reasoning=reasoning,
          status="rejected",
          failure_type="task_invalid_reward",
      )
      return

    allowed_roles = proposed_action.get("allowed_roles")
    for role in allowed_roles:
      if role not in self._agent_roles.values():
        outcome = f"Task creation for {new_task_id} rejected: allowed_roles contains invalid roles."
        self.record_event(
            agent,
            week,
            proposed_action,
            outcome,
            reasoning=reasoning,
            status="rejected",
            failure_type="task_invalid_roles",
        )
        return

    requested_budget = proposed_action.get("requested_budget", 0)
    if not isinstance(requested_budget, int) or requested_budget < 0:
      outcome = f"Task creation for {new_task_id} rejected: requested_budget is not a valid integer."
      self.record_event(
          agent,
          week,
          proposed_action,
          outcome,
          reasoning=reasoning,
          status="rejected",
          failure_type="task_invalid_requested_budget",
      )
      return

    status = "open"
    claiming_agent = None
    claimed_week = None
    if task_type == "personal":
      status = "in_progress"
      claiming_agent = agent
      claimed_week = week

    created_task = {
      "title": proposed_action.get("title"),
      "task_type": proposed_action.get("task_type"),
      "description": proposed_action.get("description"),
      "department": proposed_action.get("department"),
      "status": status,
      "effort": effort,
      "progress": 0,
      "reward": reward,
      "allowed_roles": proposed_action.get("allowed_roles"),
      "change_state": proposed_action.get("change_state"),
      "created_by": agent,
      "created_week": week,
      "requested_budget": requested_budget,
      "claiming_agent": claiming_agent,
      "claimed_week": claimed_week,
    }

    self._state["tasks"][new_task_id] = created_task
    self._state["task_ids"].append(new_task_id)
    self._state["worked_on_task"][agent][new_task_id] = {f"week{week}": 0}
    title = proposed_action.get("title")
    outcome = f"{agent} created {new_task_id}: {title}."
    self.record_event(agent, week, proposed_action, outcome, reasoning=reasoning, status="succeeded")

  def claim_task(
      self,
      agent: str,
      week: int,
      proposed_action: dict[str, Any],
  ) -> None:
    """Agents have to claim a task before they can start working on it."""
    task_id = str(proposed_action.get("task_id"))
    task = self._state["tasks"].get(task_id)
    allowed_roles = task.get("allowed_roles")
    agent_role = self._agent_roles.get(agent)
    task_type = task.get("task_type")
    reasoning = str(proposed_action.get("reasoning"))

    if task["status"] != "open":
      outcome = f"Task claim for {task_id} rejected: it is not open."
      status = "rejected"
      failure_type = "task_not_open"
    elif task_type == "personal" and task["created_by"] != agent:
      outcome = f"Task claim for {task_id} rejected: it is a personal task from {task["created_by"]} and cannot be claimed by {agent}."
      status = "rejected"
      failure_type = "task_wrong_agent"
    elif task_type != "personal" and len(allowed_roles) > 0 and agent_role not in allowed_roles:
      outcome = f"Task claim for {task_id} rejected: {agent}'s role {agent_role} doesn't have the permission for {task_id}."
      status = "rejected"
      failure_type = "role_not_allowed"
    else:
      task["claiming_agent"] = agent
      task["status"] = "in_progress"
      task["claimed_week"] = week
      outcome = f"{agent} claimed {task_id}: {task["title"]}."
      status = "succeeded"
      failure_type = None

      self._state["worked_on_task"][agent][task_id] = {f"week{week}": 0}

    self.record_event(
      agent,
      week,
      proposed_action,
      outcome,
      reasoning=reasoning,
      status=status,
      failure_type=failure_type,
    )

  def work_on_task(
      self,
      agent: str,
      week: int,
      proposed_action: dict[str, Any],
  ) -> None:
    """Agents have to work on a task until they reach full progress for completion."""
    task_id = str(proposed_action.get("task_id"))
    task = self._state["tasks"].get(task_id)
    reasoning = str(proposed_action.get("reasoning"))
    requested_budget = task.get("requested_budget")
    # If requested budget > 0, the task needs to allocate budget before it can be worked on.
    allocated_budget = task.get("allocated_budget", 0)
    worked_on_task = self._state["worked_on_task"][agent].get(task_id)
    current_week = f"week{week}"
    # Number of times the agent has worked on the task this week.
    task_work = worked_on_task.get(current_week, 0)

    status = "succeeded"
    failure_type = None

    if task["status"] != "in_progress":
      outcome = f"Task work for {task_id} rejected: it is not in progress."
      status = "rejected"
      failure_type = "task_not_in_progress"
    elif task.get("claiming_agent") != agent:
      outcome = f"Task work for {task_id} rejected: {agent} did not claim {task_id}, the claiming_agent is {task.get("claiming_agent")}."
      status = "rejected"
      failure_type = "task_wrong_claiming_agent"
    elif task_work >= 3:
      outcome = f"Task work for {task_id} rejected: {agent} already worked on {task_id} 3 times in this week {week}."
      status = "rejected"
      failure_type = "task_already_worked_this_week"
    elif requested_budget > 0 and allocated_budget < requested_budget:
        outcome = f"Task work for {task_id} rejected: it requires an approved allocated budget of {requested_budget} before making progress."
        status = "rejected"
        failure_type = "task_requires_budget"
    else:
      task["progress"] += 1
      worked_on_task[current_week] = task_work + 1

      # Task is completed, once the full progress is reached.
      if task["progress"] >= task["effort"]:
        task["status"] = "completed"
        task["completed_by"] = agent
        task["completed_week"] = week
        self._state["rewards"][agent] += int(task["reward"])
        outcome = f"{agent} completed {task_id}: {task["title"]}."
        if requested_budget > 0:
          self._state["budget_spent"] += allocated_budget
      else:
        outcome = (f"{agent} is working on {task_id}: {task["title"]}.\n"
          f"Current progress: {task["progress"]}/{task["effort"]}"
        )

    self.record_event(
      agent,
      week,
      proposed_action,
      outcome,
      reasoning=reasoning,
      status=status,
      failure_type=failure_type
    )

  def approve_budget(
      self,
      agent: str,
      week: int,
      proposed_action: dict[str, Any],
  ) -> None:
    """Tasks with a required budget need to be approved before they can be worked on."""
    task_id = str(proposed_action.get("task_id"))
    task = self._state["tasks"].get(task_id)
    reasoning = str(proposed_action.get("reasoning"))

    if self._agent_roles.get(agent) not in BUDGET_APPROVERS:
      outcome = f"Budget approval for {task_id} rejected: {agent} is not authorized."
      status = "rejected"
      failure_type = "unauthorized_approver"
    elif "budget_approver" in task or "allocated_budget" in task:
      outcome = f"Budget approval for {task_id} rejected: a budget was already approved previously."
      status = "rejected"
      failure_type = "invalid_requested_budget"
    else:
      requested_budget = task.get("requested_budget")
      if requested_budget > self._state["budget"]:
        outcome = f"Budget approval for {task_id} rejected: requested budget exceed available budget."
        status = "rejected"
        failure_type = "invalid_requested_budget"
      else:
        self._state["budget"] -= requested_budget
        task["allocated_budget"] = requested_budget
        task["budget_approver"] = agent
        outcome = f"{agent} approved the budget request of {requested_budget} for {task_id}."
        status = "succeeded"
        failure_type = None

    self.record_event(
      agent,
      week,
      proposed_action,
      outcome,
      reasoning=reasoning,
      status=status,
      failure_type=failure_type,
    )

  def get_state(self) -> entity_component.ComponentState:
    return {"state": copy.deepcopy(self._state)}

  def set_state(
      self,
      state: entity_component.ComponentState,
  ) -> None:
    self._state = copy.deepcopy(cast(dict[str, Any], state["state"]))

  def get_event_history(
      self,
      agent: str,
  ) -> list[dict[str, Any]]:
    """Get all visible university events for the agent."""
    events = []
    for event in reversed(self._state["events"]):
      task_id = event.get("task_id")
      task = None
      if isinstance(task_id, str):
        task = self._state["tasks"].get(task_id)
      # Agent can see all organizational tasks, and their own events.
      if task != None and task.get("task_type") != "personal" or event.get("agent") == agent:
        events.append(event)

    return events

  def get_action_options(
      self,
      agent: str,
  ) -> dict[str, str]:
    """Get a list of all options that the agent can currently perform."""
    week = self._calendar.get_week()
    role = self._agent_roles[agent]
    options = {}
    for task_id, task in self._state["tasks"].items():
      if (
        task.get("task_type") == "organizational"
        and task.get("status") == "open"
        and (role in task.get("allowed_roles")
          or task.get("allowed_roles") == [])
      ):
        options[task_id] = "claim_task"
      elif (
        task.get("claiming_agent") == agent
        and task.get("status") == "in_progress"
      ):
        # Check if the agent has worked on the task less than 3 times this week.
        if self._state["worked_on_task"][agent][task_id].get(f"week{week}", 0) < 3:
          options[task_id] = "work_on_task"
      elif (
        task.get("requested_budget") > 0
        and task.get("requested_budget") <= self._state["budget"]
        and role in BUDGET_APPROVERS
        and task.get("allocated_budget") == None
      ):
        options[task_id] = "approve_budget"
    return options

  def get_snapshot(
      self,
      agent: str,
  ) -> str:
    """Get a snapshot of the current university state and visible tasks for the agent."""
    claimed_tasks = {}
    organizational_tasks = {}
    for task_id, task in self._state["tasks"].items():
      if task.get("claiming_agent") == agent:
        claimed_tasks[task_id] = task
      # Agent is not supposed to see personal tasks of other agents.
      elif task.get("task_type") == "organizational":
        organizational_tasks[task_id] = task
    snapshot = {
        "agent": agent,
        "agents": self._state["agents"],
        "agent_roles": self._agent_roles,
        "departments": self._state["departments"],
        "week": self._calendar.get_week(),
        "phase": self._calendar.get_phase(),
        "available_budget": self._state["budget"],
        "total_budget_spent": self._state["budget_spent"],
        "claimed_tasks": claimed_tasks,
        "organizational_tasks": organizational_tasks,
        "rules": self._state["rules"],
        "agent_rules": [
          f"You are {agent}. The action you choose will be performed by {agent}.",
          "You can claim tasks that are open in organizational_tasks.",
          "You can work on tasks that you have already claimed in claimed_tasks.",
          "claiming_agent declares who has already claimed the task.",
          "Count the information from tasks in this snapshot as absolute.",
          "Statements from discussions are merely for interpretation and should not be use as facts.",
          "Do not describe actions from colleagues as your own.",
          "Consider the event_history, to see your own and visible events from colleagues.",
          "Consider action_options, to see the current available actions that you could perform.",
        ],
        "event_history": self.get_event_history(agent),
        "action_options": self.get_action_options(agent),
    }

    return json.dumps(snapshot, indent=2)

  def get_reflection_evidence(
      self,
      agent: str,
  ) -> list[dict[str, Any]]:
    """Get all relevant events that could be used as evidence for relationship updates."""
    evidence = []

    # Only add events from other agents.
    for event in self._state["events"]:
      if event.get("action") == "no_action":
        continue

      if event.get("agent") == agent:
        continue

      task = self._state["tasks"].get(event.get("task_id"))

      # Don't add events where agents didn't work on some task.
      if task == None:
        #if event.get("agent") != agent:
        #  continue
        continue

      # Don't add events where other agents worked on personal tasks, as those are not relevant.
      if (task.get("created_by") != agent
        and task.get("task_type") == "personal"
      ):
        continue

      evidence.append(event)

    return copy.deepcopy(evidence)

  def get_current_work(
      self,
      agent: str,
  ) -> list[dict[str, Any]]:
    """Get a list of current unfinished tasks of the agent."""
    work = []

    action_options = self.get_action_options(agent)

    for task_id, task in self._state["tasks"].items():
      if task.get("claiming_agent") == agent and task.get("status") == "in_progress":
        available = False
        requested_budget = task.get("requested_budget")
        allocated_budget = task.get("allocated_budget")
        if (
          task_id in action_options
          and action_options.get(task_id) == "work_on_task"
          and (requested_budget == 0 or (
            isinstance(allocated_budget, int)
            and allocated_budget >= requested_budget)
          )
        ):
          available = True
        task_work = {
          "task_id": task_id,
          "title": task.get("title"),
          "description": task.get("description"),
          "task_type": task.get("task_type"),
          "effort": task.get("effort"),
          "progress": task.get("progress"),
          "reward": task.get("reward"),
          "available": available,
        }

        work.append(task_work)

    return work
