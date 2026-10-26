ORGANIZATION = "TU Darmstadt"
DEPARTMENTS = ["Department of Computer Science"]

DEPARTMENT_CHAIR = {"Department of Computer Science": "Alice"}

AGENTS = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry", "Iris", "Jack"]

BUDGET = 10000

TASKS = {
    "task1": {
        "title": "Research Collaboration",
        "description": (
            "Develop a research idea, identify collaborators, and prepare "
            "the application."
        ),
        "department": "Department of Computer Science",
        "status": "open",
        "effort": 2,
        "progress": 0,
        "reward": 3,
        #"allowed_roles": [
        #    "Research Coordinator",
        #    "Research Professor",
        #],
        "allowed_roles": [], # if empty, then any role can complete the task.
        "change_state": True,
    },
}

RULES = [
    "Only authorized roles can claim tasks.",
    "Only the claiming agents can complete a task.",
    "Spending must be positive and cannot exceed the budget.",
    "Every decision requires a reasoning.",
]

WEEKS = 6
COMMUNICATION_ROUNDS_PER_WEEK = 2
PLANNING_ROUNDS_PER_WEEK = 1
ADMINISTRATION_ROUNDS_PER_WEEK = 3
REFLECTION_ROUNDS_PER_WEEK = 1
MAX_STEPS = 500

PREMISE = (
    f"The department is operating over a {WEEKS}-week academic term. "
    "Agents must make decisions while following university policy."
)

START_DATE = "2026-09-01"

NUM_AGENTS = len(AGENTS)

PERSONA_SEED = 42
