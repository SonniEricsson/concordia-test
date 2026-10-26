import datetime
import json
from concordia.prefabs import entity as entity_prefabs
from concordia.prefabs import game_master as game_master_prefabs
from concordia.prefabs.game_master import dialogic_and_dramaturgic
from concordia.typing import entity as entity_lib
from concordia.typing import prefab as prefab_lib
from concordia.typing import scene as scene_lib
from concordia.utils import helper_functions
from concordia.language_model import language_model
from concordia.components.game_master import event_resolution
from concordia.components.game_master import make_observation as make_observation_component_module
from typing import Any, Callable
from concordia.prefabs.simulation import generic as simulation_lib
from university.components.academic_calendar import AcademicCalendar
from university.components.university_state import UniversityState
from university.components.relationship_state import RelationshipState
from university.components.communication_state import CommunicationState, DEFAULT_MAX_MESSAGE_WORDS
from university.components.weekly_plan import WeeklyPlan, DEFAULT_MAX_PLAN_WORDS
from university.config import personas

def configure_discussion_scene(
    people: list[str],
    config: Any,
    week: int,
) -> list[scene_lib.SceneSpec]:
  """Create the scenes for private communication and planning."""
  discussion_scenes = []

  # Build premise for planning scene.
  planning_premise = {}
  for person in people:
    planning_premise[person] = [
        f"It is the planning stage of week {week}. "
        "Private communication has ended. "
        "Use the information you gathered to create your weekly plan."
    ]

  # Build prompt for communication scene.
  for index in range(1, config.COMMUNICATION_ROUNDS_PER_WEEK + 1):
    communication_type = scene_lib.SceneTypeSpec(
        name=f"week_{week:02}_communication_{index:02}",
        game_master_name="university rules",
        action_spec=entity_lib.free_action_spec(
            call_to_action=(
                "Send private messages to your colleagues.\n"
                "Your goal is to gather enough information to then create your weekly plan.\n"
                "Read CURRENT PRIVATE MESSAGES and AUTHORITATIVE UNIVERSITY STATE.\n"
                "Coordinate responsibilities and identify priorities with your colleagues.\n"
                "You can ask each other questions, clarify dependencies and make plans.\n"
                "You also have access to older messages.\n"
                "Private messages are claims and should not be treated as verified university facts.\n"
                "Do not invent information, tasks, results or approvals.\n"
                f"A message should have at most {DEFAULT_MAX_MESSAGE_WORDS} words.\n"
                "Return exactly one JSON object without Markdown formatting:\n"
                '{"private_messages":[{"recipient":"Alice","message":"..."}]}\n'
                "Use exact colleague names. Do not message yourself.\n"
                "private_messages should contain direct messages to individual colleagues.\n"
                "If you don't send any private messages, use an empty list.\n"
            ),
            tag="communication",
        ),
    )

    # Build premise for communication scene.
    communication_premise = {}
    for person in people:
      communication_premise[person] = [
          f"It is the communication stage {index} of week {week}. "
          "Communicate with your colleagues to get an idea on how you should plan your week "
          "and what tasks you could do. "
          "Planning follows after all communication stages."
      ]

    discussion_scenes.append(scene_lib.SceneSpec(
        scene_type=communication_type,
        participants=people,
        num_rounds=len(people),
        premise=communication_premise,
    ))

  # Build prompt for planning scene.
  planning_type = scene_lib.SceneTypeSpec(
      name=f"week_{week:02}_planning",
      game_master_name="university rules",
      action_spec=entity_lib.free_action_spec(
          call_to_action=(
              "Private communication has ended. Create your weekly plan.\n"
              "Read CURRENT PRIVATE MESSAGES, AUTHORITATIVE UNIVERSITY STATE, "
              "and CURRENT WEEKLY PLAN, to see the plan of the previous week.\n"
              f"Create a new weekly plan consisting of less than {DEFAULT_MAX_PLAN_WORDS} words.\n"
              f"You will have {config.ADMINISTRATION_ROUNDS_PER_WEEK} administrative turns this week.\n"
              "Propose a short, prioritized work plan covering those turns.\n"
              "Keep in mind that creating tasks, claiming tasks, approving budgets, "
              "and working require separate actions.\n"
              "If you are required to wait for an action of another colleague, "
              "determine what other useful work you could do in the meantime.\n"
              "Propose new tasks for distinct, useful work that has not been created yet.\n"
              "Treat only AUTHORITATIVE UNIVERSITY STATE, configured memories, "
              "and verified evidence as facts. Previous agent statements are claims, "
              "not verified facts.\n"
              "Do not invent information that has not existed previously and is not "
              "backed by facts.\n"
              "Do not invent a task_id, instead refer to their title "
              "or use the task_id from AUTHORITATIVE UNIVERSITY STATE.\n"
              "Always try to find some work, and if nothing is available, state it explicitly.\n"
              "Your plan will be public. Do not share private information "
              "unless you actively choose to share it.\n"
              "Return exactly one JSON object without Markdown formatting:\n"
              '{"weekly_plan":"..."}\n'
          ),
          tag="planning",
      ),
  )

  discussion_scenes.append(scene_lib.SceneSpec(
      scene_type=planning_type,
      participants=list(people),
      num_rounds=config.PLANNING_ROUNDS_PER_WEEK * len(people),
      premise=planning_premise,
  ))

  return discussion_scenes

# Similar to simulation.py from pub_coordination, state_formation and signaling.
def configure_scenes(
    people: list[str],
    config: Any,
) -> list[scene_lib.SceneSpec]:
  """Create all scenes for private communication, planning, administration and reflection."""
  scenes = []

  for week in range(1, config.WEEKS + 1):
    #discussion_premise = {}
    administration_premise = {}
    reflection_premise = {}
    # Build premises for administration and reflection scenes.
    for person in people:
      #discussion_premise[person] = [
      #  f"It is the discussion phase of week {week}. "
      #  "Review what has already been said before responding. "
      #  "The discussion should determine a feasible work plan for the current week "
      #  "with tasks, responsibilities, priorities and plans for further steps. "
      #  "Do not restate earlier positions."
      #]
      administration_premise[person] = [
        f"It is the administrative phase of week {week}. "
        "Inspect the authoritative university state and choose actions "
        "to work on your weekly plan and advance the current tasks. "
        "Your chosen actions should be consistent with your role and permissions."
      ]
      reflection_premise[person] = [
        f"It is the reflection phase of week {week}. "
        "The administration phase of the week has just ended, "
        "now you're privately reflecting on your relationships with your colleagues "
        "and your new experiences since the last reflection. "
        "Determine new relationship changes."
      ]

    scenes.extend(configure_discussion_scene(people, config, week))

    # Build prompt for administration scene.
    administration_type = scene_lib.SceneTypeSpec(
      name=f"week_{week:02}_administration",
      game_master_name="university rules",
      action_spec=entity_lib.free_action_spec(
      call_to_action=(
          "Read CURRENT WEEKLY PLAN that you established during discussion.\n"
          "Determine whether the steps are currently feasible.\n"
          "Try to follow that plan and choose one action that will make progress in that direction.\n"

          "Read AUTHORITATIVE UNIVERSITY STATE before choosing an action.\n"
          "Only treat that state, configured memories, and verified evidence as facts. "
          "Previous agent statements are claims, not verified facts.\n"
          "Use the exact title, department, status, owner, and permissions shown there.\n"
          "Do not claim that work, evidence, findings, approvals, or spendings exist "
          "unless it is recorded in the authoritative state.\n"
          "If no legal action advances your weekly plan, create a task with create_task or return no_action.\n"
          "Do not repeat an action that previously failed unless you have changed "
          "the fields that caused the failure.\n"

          "Create a task with create_task only when no existing task represents the work.\n"
          "The task_type can be either personal or organizational, "
          "where personal means that only the creator can complete the task, "
          "while organizational tasks can be completed by other agents.\n"
          "When creating a task, consider if it needs a budget in order to be completed.\n"
          "A task has to be claimed first before it can be worked on.\n"
          "If it is a personal task, then it is claimed by the creating agent during create_task.\n"
          "If it is an organizational task, it has to be claimed in a later action with claim_task.\n"
          "The reward for a task has to be 1-10.\n"
          "In order to make progress on a task, use work_on_task.\n"
          "When using work_on_task, the task has to be from claimed_tasks with the status in_progress.\n"
          "Each time work_on_task is executed for a task, it's progress is incremented, "
          "until it reaches the required effort.\n"
          "Once the required effort for a task has been reached, it is marked as completed.\n"
          "allowed_roles in tasks should only contain roles from agent_roles from the university state.\n"
          "An empty list for allowed_roles in a task means all agent_roles can claim the task.\n"

          "A task has requested_budget, which can be either some budget needed to complete it or 0.\n"
          "Before a task with a requested_budget > 0 can be worked on, the budget has to be approved "
          "and allocated by a Department Chair or Budget Officer with approve_budget.\n"
          "The currency is Euro. Use for example 2000 EUR.\n"

          "CONSIDER THESE OPTIONS WHEN CHOOSING AN ACTION:\n"
          "If you want to create a new task, use create_task.\n"
          "If you don't choose any action, use no_action.\n"
          "When choosing an action other than create_task or no_action, "
          "consider the available options from action_options in your authoritative snapshot.\n"

          "Read CURRENT UNFINISHED TASKS before choosing an action.\n"
          "Try to work on the tasks listed there before choosing no_action.\n"
          "The list of unfinished_tasks should be worked on as much as possible, so no unfinished tasks are open.\n"
          "Do not state that all tasks have been completed while unfinished_tasks still contains tasks.\n"
          "Tasks with available=false may be currently blocked by something else and require waiting or another action.\n"

          "Return one JSON object without Markdown formatting using one of these forms:\n"
          '{"action":"create_task","title":"...","task_type":"organizational",'
          '"description":"...","department":"Department of Computer Science","effort":2,'
          '"reward":2,"allowed_roles":[],"requested_budget":0,"change_state":true,"reasoning":"..."}\n'
          '{"action":"claim_task","task_id":"...","reasoning":"..."}\n'
          '{"action":"work_on_task","task_id":"...","reasoning":"..."}\n'
          '{"action":"approve_budget","task_id":"...","reasoning":"..."}\n'
          '{"action":"no_action","reasoning":"..."}\n'
      ),
        tag="administration",
      ),
    )

    scenes.append(
      scene_lib.SceneSpec(
        scene_type=administration_type,
        participants=people,
        num_rounds=config.ADMINISTRATION_ROUNDS_PER_WEEK * len(people),
        premise=administration_premise,
      )
    )

    # Build prompt for reflection scene.
    reflection_type = scene_lib.SceneTypeSpec(
        name=f"week_{week:02}_reflection",
        game_master_name="university rules",
        action_spec=entity_lib.free_action_spec(
            call_to_action=(
              "Reflect on your relationships, observations, discussions and events "
              f"that have happened in this week {week}.\n"
              "Make an update on your relationship scores with your colleagues.\n"
              "Read CURRENT RELATIONSHIP STATES, and "
              "CURRENT PRIVATE MESSAGES before choosing an update.\n"

              "reflection_agent defines the reflecting agent.\n"
              "current_relationships contains the absolute scores for the agent's relationships.\n"
              "recent_events contains events as evidence for the update since the previous reflection.\n"
              "Your relationships could either stay the same, improve or worsen.\n"
              "They are based on the dimensions trust and respect.\n"
              "Trust is about honesty and reliability.\n"
              "Respect is about competence and judgement.\n"
              "The scores should be integers and range from -10 to 10, where 0 means neutral or it hasn't been established.\n"
              "These scores should represent your opinion about your colleagues, not their opinion of you.\n"
              "Updates of the relationship scores should be justified on recent events.\n"
              "Cite event_ids as evidence_ids for each update to justify them. Every cited event must describe the target's action.\n"
              "evidence_ids have to actually be in recent_events.\n"
              "Consider both successful and rejected actions as evidence.\n"
              "Success does not automatically justify an increase, and rejection "
              "does not automatically justify a decrease.\n"
              "Do not invent events that have not happened.\n"
              "Do not infer colleague's private opinions of you.\n"

              "Return exactly one JSON object without Markdown formatting:\n"
              '{"action":"update_relationship","updates":[{"target":"...",'
              '"scores":{"trust":1,"respect":1},"evidence_ids":[6,7],"reasoning":"..."}]}\n'
              "Updates can include multiple people. Only include colleagues with relationship changes.\n"
              "If there are no relationship changes, then updates should be an empty list and the JSON should look like this:\n"
              '{"action":"update_relationship","updates":[]}\n'
              "The given scores in the update will be set as the absolute new scores, not added or subtracted.\n"
              "Consider your current relationship scores before setting new scores.\n"
              "Do not include yourself for relationship updates.\n"
            ),
            tag="reflection",
        ),
    )

    scenes.append(
      scene_lib.SceneSpec(
        scene_type=reflection_type,
        participants=people,
        num_rounds=config.REFLECTION_ROUNDS_PER_WEEK * len(people),
        premise=reflection_premise,
      )
    )

  return scenes

def run_simulation(
    config: Any,
    model: language_model.LanguageModel,
    embedder: Callable[[str], Any],
) -> dict[str, Any] | None:
  """Build and run the university simulation."""

  agent_names = getattr(config, "AGENTS", None)
  num_agents = getattr(config, "NUM_AGENTS", 3)
  # Load persona profiles for agents.
  profiles = personas.load_personas(
      names=agent_names,
      num_agents=num_agents,
      seed=getattr(config, "PERSONA_SEED", 42),
  )

  agents = []
  agent_roles = {}
  for profile in profiles:
    agents.append(profile.name)
    agent_roles[profile.name] = profile.role

  # Create scenes.
  scenes = configure_scenes(agents, config)

  total_actions = 0
  for scene in scenes:
    total_actions += scene.num_rounds

  # max_steps = getattr(config, "MAX_STEPS", config.WEEKS * (len(agents) * (config.DISCUSSION_ROUNDS_PER_WEEK + config.ADMINISTRATION_ROUNDS_PER_WEEK)))
  max_steps = getattr(config, "MAX_STEPS", total_actions + 1)

  if total_actions > max_steps:
    raise ValueError(
        f"Total actions ({total_actions}) exceeds max_steps({max_steps})."
    )

  prefabs = {
      **helper_functions.get_package_classes(entity_prefabs),
      **helper_functions.get_package_classes(game_master_prefabs),
  }

  prefabs["university_rules__GameMaster"] = (
    dialogic_and_dramaturgic.GameMaster()
  )

  calendar = AcademicCalendar(
      start_date=datetime.date.fromisoformat(config.START_DATE),
  )

  relationships = RelationshipState(
    agents=agents,
    departments=config.DEPARTMENTS,
    calendar=calendar,
  )

  university = UniversityState(
      agents=agents,
      organization=config.ORGANIZATION,
      departments=config.DEPARTMENTS,
      budget=config.BUDGET,
      tasks=config.TASKS,
      rules=config.RULES,
      agent_roles=agent_roles,
      calendar=calendar,
  )

  communication = CommunicationState(
    agents=agents,
    calendar=calendar,
  )

  weekly_plan = WeeklyPlan(calendar=calendar)

  # Agents first make a proposal, then proposal should be resolved during event resolution.
  def resolve_conclusion(
      document,
      premise,
      active_player_name,
  ):
    """Resolve agent action and before it is propagated to the agents."""
    phase = calendar.get_phase()

    # Event resolution from components\game_master\event_resolution.py
    event_resolver = university.get_entity().get_component(
      event_resolution.DEFAULT_RESOLUTION_COMPONENT_KEY,
      type_=event_resolution.EventResolution,
    )

    agent = event_resolver.get_active_entity_name()
    proposed_action = event_resolver.get_putative_action()

    # For adding observations to current acting agent directly.
    make_observation = university.get_entity().get_component(
      make_observation_component_module.DEFAULT_MAKE_OBSERVATION_COMPONENT_KEY,
      type_=make_observation_component_module.MakeObservation,
    )

    # Determine whether an agent is proposing an action and it's not a GM action.
    if agent is None or proposed_action is None:
      return None

    conclusion = ""
    # Resolve action during communication scene.
    if phase == "communication":
      try:
        messages = communication.send_messages(active_player_name, proposed_action)
        processed_messages = []
        for message in messages:
          processed_messages.append(json.dumps(message, indent=2))
        # Add private messages to observations of acting agent.
        observation = "Private Communication Feedback:\n" + "\n".join(processed_messages)
        make_observation.add_to_queue(active_player_name, observation)
        # Public conclusion that all agents can see.
        conclusion = f"PRIVATE COMMUNICATION for {active_player_name} has ended."
      except ValueError as error:
        error_observation = f"Private Communication Feedback: {error}"
        # Send error information only to the acting agent.
        make_observation.add_to_queue(active_player_name, error_observation)
        conclusion = f"PRIVATE COMMUNICATION for {active_player_name} was rejected."

    # Resolve action during planning scene.
    if phase == "planning":
      action = weekly_plan.resolve_action(active_player_name, proposed_action)
      if action.get("status") == "succeeded":
        conclusion = f"WEEKLY PLAN for {active_player_name}: {action.get("plan")}"
      elif action.get("status") == "rejected":
        conclusion = f"WEEKLY PLAN for {active_player_name} was rejected: {action.get("plan")}"

    # Resolve action during administration scene.
    if phase == "administration":
      action = university.resolve_action(active_player_name, proposed_action)

      observation = {}

      organizational_keys = ["event_id", "event_type", "agent", "action", "task_id", "week", "outcome", "status", "failure_type"]
      personal_keys = ["event_id", "event_type", "agent", "action", "task_id", "week"]

      task_type = ""
      if action.get("task_id") != None:
        task = university._state["tasks"].get(action["task_id"])
        if task != None:
          task_type = task.get("task_type")

      if task_type == "personal":
        for key in personal_keys:
          observation[key] = action[key]
        observation["outcome"] = "Outcome of this event is not visible, because it is a personal task."
        agent_observation = f"Administration Feedback: {action.get("outcome")}"
        # Send individual observation only to acting agent for full information feedback.
        make_observation.add_to_queue(active_player_name, agent_observation)

      else:
        for key in organizational_keys:
          observation[key] = action[key]

      conclusion = f"AUTHORITATIVE UNIVERSITY ACTION for {active_player_name}: " + json.dumps(observation, indent=2)

    # Resolve action for reflection scene.
    elif phase == "reflection":
      evidence = university.get_reflection_evidence(active_player_name)
      updates = relationships.resolve_update(active_player_name, proposed_action, evidence)
      update_outcomes = []
      successes = 0
      rejections = 0
      for update in updates:
        if update["status"] == "succeeded":
          successes += 1
        elif update["status"] == "rejected":
          rejections += 1
        update_outcomes.append("Reflection " + str(update.get("reflection_id")) + ": " + update.get("outcome"))

      # Send individual observation only to acting agent for full information feedback.
      agent_observation = "Reflection Feedback:\n" + "\n".join(update_outcomes)
      make_observation.add_to_queue(active_player_name, agent_observation)

      # Only publicly record the status of updates, not the actual values, so they stay private.
      conclusion = f"RELATIONSHIP REFLECTION FOR {active_player_name}: {successes} succeeded, {rejections} rejected."

    return conclusion

  # Extra components for the game master.
  components = {
      "University state": university,
      "Academic calendar": calendar,
      "Relationship states": relationships,
      "Communication state": communication,
      "Weekly plans": weekly_plan
  }

  # Create the agents with necessary components.
  agent_instances, agent_memories = personas.make_agents(
    profiles=profiles,
    university=university,
    relationships=relationships,
    communication=communication,
    plan=weekly_plan,
    prefab=getattr(config, "AGENT_PREFAB", "basic__Entity"),
  )

  instances = list(agent_instances)

  instances.append(
    prefab_lib.InstanceConfig(
      prefab="formative_memories_initializer__GameMaster",
      role=prefab_lib.Role.INITIALIZER,
      params={
        "name": "initial setup rules",
        "next_game_master_name": "university rules",
        "shared_memories": [
          (
            f"{config.ORGANIZATION} contains the {config.DEPARTMENTS[0]}. "
            f"The department has {config.NUM_AGENTS} agents and a finite operating budget of {config.BUDGET}."
          ),
          config.PREMISE,
        ],
        "player_specific_memories": agent_memories,
        "skip_formative_memories_for": agents,
      },
    )
  )

  instances.append(
    prefab_lib.InstanceConfig(
      prefab="university_rules__GameMaster",
      role=prefab_lib.Role.GAME_MASTER,
      params={
        "name": "university rules",
        "scenes": scenes,
        "extra_components": components,
        # Do not let LLM generate invented observations when observation queue is empty.
        "allow_llm_fallback": False,
        # Called by run_chain_of_thought() in event_resolution.
        "adjust_event_resolution": [resolve_conclusion],
      },
    )
  )

  simulation_config = prefab_lib.Config(
    default_premise=config.PREMISE,
    default_max_steps=max_steps,
    prefabs=prefabs,
    instances=instances,
  )

  sim = simulation_lib.Simulation(
      config=simulation_config,
      model=model,
      embedder=embedder,
  )

  structured_log = sim.play()

  return {
      "structured_log": structured_log,
      "university_state": university,
      "relationship_states": relationships,
      "communication_state": communication,
      "planning_state": weekly_plan,
      "agents": agents,
  }
