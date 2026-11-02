from university.config.semester import *

AGENTS = ["Alice", "Bob", "Charlie"]
NUM_AGENTS = len(AGENTS)
WEEKS = 2
TASKS = {}
COMMUNICATION_ROUNDS_PER_WEEK = 3
PLANNING_ROUNDS_PER_WEEK = 1
ADMINISTRATION_ROUNDS_PER_WEEK = 2
REFLECTION_ROUNDS_PER_WEEK = 1
MAX_STEPS = 100
PREMISE = (
    f"The department is operating over a {WEEKS}-week academic term. "
    "Agents must make decisions while following university policy."
)
