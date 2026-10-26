import datetime
import re
from typing import cast

from concordia.components.game_master import scene_tracker
from concordia.typing import entity as entity_lib
from concordia.typing import entity_component


class AcademicCalendar(
    entity_component.ContextComponent,
    entity_component.ComponentWithLogging,
):
  """A component that represents the academic calendar of the university."""

  def __init__(
      self,
      *,
      start_date: datetime.date,
      scene_tracker_key: str = scene_tracker.DEFAULT_SCENE_TRACKER_COMPONENT_KEY,
      pre_act_label: str = "\nAcademic calendar",
  ):
    super().__init__()
    self._start_date = start_date
    self._scene_tracker_key = scene_tracker_key
    self._pre_act_label = pre_act_label
    self._week = 1
    self._phase = "communication"
    self._last_timestamp = (self._week, self._phase)

  def get_week(self) -> int:
    return self._week

  def get_phase(self) -> str:
    return self._phase

  def get_pre_act_label(self) -> str:
    return self._pre_act_label

  def get_pre_act_value(self) -> str:
    return (
        f"week: {self._week}\n"
        f"phase: {self._phase}\n"
    )

  # Similarily to state_formation\simulation.py
  def pre_act(self, action_spec: entity_lib.ActionSpec) -> str:
    """Update the current week/scene before the agent acts."""
    tracker = self.get_entity().get_component(
        self._scene_tracker_key,
        type_=scene_tracker.SceneTracker,
    )

    # Prevent output of week 1 at the end once simulation is finished.
    if tracker.is_done():
      return self.get_pre_act_value()

    current_scene_type = tracker.get_current_scene_type()
    current_scene_name = current_scene_type.name

    # Check the current scene.
    match = re.fullmatch(
        r"week_(\d+)_(communication|planning|administration|reflection)(?:_\d+)?",
        current_scene_name,
    )
    if match:
      self._week = int(match.group(1))
      self._phase = match.group(2)

    current_period = (self._week, self._phase)

    # Print out the new scene name.
    if current_period != self._last_timestamp:
      self._last_timestamp = current_period
      print(
        f"\n{'=' * 60}\n"
        f"WEEK {self._week} | {self._phase.upper()}"
        f"\n{'=' * 60}\n"
      )

    result = self.get_pre_act_value()
    return result

  def get_state(self) -> entity_component.ComponentState:
    return {
        "week": self._week,
        "phase": self._phase,
    }

  def set_state(
      self,
      state: entity_component.ComponentState,
  ) -> None:
    self._week = cast(int, state["week"])
    self._phase = cast(str, state["phase"])
