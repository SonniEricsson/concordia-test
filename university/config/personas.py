import random
import json
from dataclasses import dataclass

from concordia.typing import prefab as prefab_lib
from concordia.components.agent import report_function
from university.components.university_state import UniversityState
from university.components.relationship_state import RelationshipState
from university.components.communication_state import CommunicationState
from university.components.weekly_plan import WeeklyPlan

@dataclass(frozen=True)
class AgentProfile:
    name: str
    role: str
    department: str
    background: str
    traits: str
    skillset: str
    motivation: str
    goals: tuple[str, ...] = ()
    #relationships: dict[str, dict[str, dict[str, int]]] = field(default_factory=dict)

PEOPLE: dict[str, AgentProfile] = {
    "Alice": AgentProfile(
        name="Alice",
        role="Department Chair",
        department="Computer Science",
        background="Senior faculty member with 15 years of academic experience.",
        traits="Diplomatic, organized, cautious",
        skillset="Leadership, budgeting, negotiation",
        motivation="Keep the department stable and well funded.",
        goals=(
            "Balance the department budget",
            "Support faculty research",
            "Improve student outcomes",
        ),
    ),
    "Bob": AgentProfile(
        name="Bob",
        role="Budget Officer",
        department="Computer Science",
        background="University administrator with experience in financial planning.",
        traits="Analytical, frugal, detail-oriented",
        skillset="Budgeting, forecasting, accounting",
        motivation="Maintain financial sustainability.",
        goals=(
            "Reduce unnecessary spending",
            "Track departmental expenses",
            "Build a reserve fund",
        ),
    ),
    "Charlie": AgentProfile(
        name="Charlie",
        role="Professor",
        department="Computer Science",
        background="Researcher specializing in artificial intelligence.",
        traits="Curious, ambitious, independent",
        skillset="Machine learning, research, grant writing",
        motivation="Advance AI research and gain recognition.",
        goals=(
            "Secure research funding",
            "Publish papers",
            "Hire research assistants",
        ),
    ),
    "Diana": AgentProfile(
        name="Diana",
        role="Associate Professor",
        department="Computer Science",
        background="Faculty member focused on software engineering education.",
        traits="Practical, collaborative, patient",
        skillset="Software engineering, teaching, curriculum design",
        motivation="Improve the quality of computing education.",
        goals=(
            "Modernize courses",
            "Improve teaching resources",
            "Mentor junior faculty",
        ),
    ),
    "Eve": AgentProfile(
        name="Eve",
        role="Lab Director",
        department="Computer Science",
        background="Technical researcher managing departmental computing facilities.",
        traits="Resourceful, technical, pragmatic",
        skillset="Infrastructure, procurement, systems administration",
        motivation="Keep research infrastructure reliable.",
        goals=(
            "Upgrade computing hardware",
            "Control infrastructure costs",
            "Expand lab capacity",
        ),
    ),
    "Frank": AgentProfile(
        name="Frank",
        role="Undergraduate Program Coordinator",
        department="Computer Science",
        background="Faculty member with extensive experience in undergraduate teaching.",
        traits="Approachable, organized, student-focused",
        skillset="Program planning, advising, scheduling",
        motivation="Help students complete their degrees successfully.",
        goals=(
            "Improve course scheduling",
            "Reduce student bottlenecks",
            "Increase retention",
        ),
    ),
    "Grace": AgentProfile(
        name="Grace",
        role="Research Director",
        department="Computer Science",
        background="Senior researcher coordinating several funded research groups.",
        traits="Strategic, persuasive, competitive",
        skillset="Research management, grants, partnerships",
        motivation="Increase the department's research profile.",
        goals=(
            "Win major grants",
            "Expand industry partnerships",
            "Increase research output",
        ),
    ),
    "Henry": AgentProfile(
        name="Henry",
        role="Lecturer",
        department="Computer Science",
        background="Teaching-focused faculty member with industry experience.",
        traits="Practical, energetic, adaptable",
        skillset="Programming, teaching, project supervision",
        motivation="Provide students with useful practical skills.",
        goals=(
            "Improve project-based learning",
            "Acquire better teaching tools",
            "Increase student engagement",
        ),
    ),
    "Iris": AgentProfile(
        name="Iris",
        role="Graduate Program Coordinator",
        department="Computer Science",
        background="Academic staff member experienced in graduate program administration.",
        traits="Methodical, diplomatic, conscientious",
        skillset="Administration, advising, policy interpretation",
        motivation="Make graduate programs efficient and attractive.",
        goals=(
            "Increase graduate enrollment",
            "Streamline admissions",
            "Support doctoral students",
        ),
    ),
    "Jack": AgentProfile(
        name="Jack",
        role="Department Administrator",
        department="Computer Science",
        background="Long-serving administrative staff member familiar with university procedures.",
        traits="Reliable, cautious, process-oriented",
        skillset="Administration, procurement, scheduling",
        motivation="Keep departmental operations running smoothly.",
        goals=(
            "Process purchases efficiently",
            "Avoid administrative errors",
            "Support faculty and staff",
        ),
    ),
}

# Similarily to signaling\configs\personas.py
def make_agents(
    profiles: list[AgentProfile],
    university: UniversityState,
    relationships: RelationshipState,
    communication: CommunicationState,
    plan: WeeklyPlan,
    prefab: str = "basic__Entity",
) -> tuple[
    list[prefab_lib.InstanceConfig],
    dict[str, list[str]],
    ]:

  agents = []
  memories = {}

  for persona in profiles:
    goal = (
      f"Your role is {persona.role} in the "
      f"{persona.department} department. "
      f"Your background is: {persona.background} "
      f"Your traits are: {persona.traits} "
      f"Your skillset is: {persona.skillset} "
      f"Your motivation is: {persona.motivation} "
      f"Your goals are: {' '.join(persona.goals)}"
    )

    # Agents can read current state of the University.
    university_state = report_function.ReportFunction(
        function=lambda name=persona.name: university.get_snapshot(name),
        pre_act_label="AUTHORITATIVE UNIVERSITY STATE",
    )

    # Agents receive a list of current claimed tasks that have not been completed yet.
    unfinished_tasks = report_function.ReportFunction(
       function=lambda name=persona.name: json.dumps({
          "agent": name,
          "unfinished_tasks": university.get_current_work(name),
        },
        indent=2,
      ),
      pre_act_label="CURRENT UNFINISHED TASKS",
    )

    # Agents receive an overview of their current relationships.
    relationship_state = report_function.ReportFunction(
       function=lambda name=persona.name: json.dumps(
          relationships.get_reflection_state(
            name,
            university.get_reflection_evidence(name),
          ),
          indent=2,
        ),
       pre_act_label="CURRENT RELATIONSHIP STATES",
    )

    # Agents can read all their sent and received private messages.
    communication_state = report_function.ReportFunction(
      function=lambda name=persona.name: json.dumps(
        communication.get_messages(name),
        indent=2,
      ),
      pre_act_label="CURRENT PRIVATE MESSAGES",
    )

    # Agents can read their current weekly plan.
    weekly_plan = report_function.ReportFunction(
       function=lambda name=persona.name: json.dumps(
          plan.get_plan(name),
          indent=2,
       ),
       pre_act_label="CURRENT WEEKLY PLAN",
    )

    agents.append(
      prefab_lib.InstanceConfig(
        prefab=prefab,
        role=prefab_lib.Role.ENTITY,
        params={
          "name": persona.name,
          "goal": goal,
          "prefix_entity_name": False, # Don't start answer with entity name, so answers can be only JSON.
          "extra_components": { # Need to add extra_components to basic prefab.
              "UniversityState": university_state,
              "OwnedTasks": unfinished_tasks,
              "RelationshipState": relationship_state,
              "CommunicationState": communication_state,
              "WeeklyPlan": weekly_plan,
          },
          "summarize_observations": True,
          "observation_history_length": 30,
          "observation_summary_batch_size": 20,
          "observation_summary_max_tokens": 400,
          # Set these parameters to 0, so agents don't retrieve observations that have already been summarized.
          "situation_perception_history_length": 0, # Determines situation.
          "self_perception_history_length": 0, # Determines the personality.
          "person_by_situation_history_length": 0, # Determines the fitting action for the situation.
        },
      )
    )

    memories[persona.name] = [
      f"Role: {persona.role}.",
      f"Background: {persona.background}",
      f"Traits: {persona.traits}",
      f"Skillset: {persona.skillset}",
      f"Motivation: {persona.motivation}",
      f"Goals: {' '.join(persona.goals)}",
    ]

  return agents, memories

def load_personas(
    names: list[str] | None = None,
    num_agents: int | None = None,
    seed: int = 42,
) -> list[AgentProfile]:
    """Load explicitly selected or randomly sampled personas."""
    selected_agents = []

    # names contains specific personas that should be loaded.
    if names != None:
      unknown = names - PEOPLE.keys()
      if len(unknown) > 0:
        raise ValueError(
          f"Unknown personas: {unknown}"
        )

      selected_agents = []
      for name in names:
        selected_agents.append(PEOPLE[name])

    # personas will be loaded randomly.
    else:
      if num_agents is None:
        raise ValueError(
          "num_agents has not been provided."
        )

      if not 0 < num_agents <= len(PEOPLE):
        raise ValueError(
          f"num_agents must be between 1 and {len(PEOPLE)}."
        )

      rng = random.Random(seed)
      selected_names = rng.sample(
          list(PEOPLE.keys()),
          k=num_agents,
      )

      for name in selected_names:
        selected_agents.append(PEOPLE[name])

    return selected_agents
