import copy
from typing import Any, cast
from concordia.typing import entity_component
from university.components.academic_calendar import AcademicCalendar

class UniversityInformation(
  entity_component.ContextComponent,
  entity_component.ComponentWithLogging,
):
  """A component that stores relevant information for departments."""

  def __init__(
      self,
      *,
      calendar: AcademicCalendar,
      departments: list[str],
      agent_departments: dict[str, str],
  ):
    super().__init__()

    self._calendar = calendar
    self._departments = list(departments)
    self._agent_departments = agent_departments

    self._state = {
      "all_information": {},
      "history": [],
    }

  def record_information(
      self,
      *,
      info_id: str | None = None,
      title: str,
      department: str | None = None,
      content: str,
  ) -> dict[str, Any]:
    """Record new information in the state."""
    status = "succeeded"
    failure_type = None
    all_information = self._state["all_information"]

    if info_id != None and info_id not in all_information:
      status = "rejected"
      failure_type = "invalid_information_id"
    #if not isinstance(info_id, str) or info_id == "":
    #  status = "rejected"
    #  failure_type = "invalid_information_id"
    elif not isinstance(title, str) or title == "":
      status = "rejected"
      failure_type = "invalid_information_title"
    elif department != None and department not in self._departments:
      status = "rejected"
      failure_type = "invalid_department"
    elif not isinstance(content, str) or content == "":
      status = "rejected"
      failure_type = "invalid_information_content"

    if info_id == None:
      info_id = f"info{len(all_information) + 1}"
      #all_information[info_id] = []
    old_information = all_information.get(info_id)
    updated_week = self._calendar.get_week()
    recorded_week = updated_week
    revision = 1
    if old_information != None:
      recorded_week = old_information["recorded_week"]
      revision = old_information["revision"] + 1

    information = {
      "info_id": info_id,
      "title": title,
      "department": department,
      "content": content,
      "recorded_week": recorded_week,
      "updated_week": updated_week,
      "revision": revision,
      "status": status,
      "failure_type": failure_type,
    }

    if status == "succeeded":
      all_information[info_id] = information
    self._state["history"].append({
      "department": department,
      "info_id": info_id,
      "previous_information": old_information,
      "updated_information": information,
    })

    return information

  def get_information(
      self,
      agent: str,
      info_id: str,
  ) -> dict[str, Any] | None:
    information = self._state["all_information"].get(info_id)
    if information == None:
      return None
    info_department = information["department"]
    agent_department = self._agent_departments.get(agent)
    if info_department != [] and agent_department != info_department:
      return None

    return copy.deepcopy(information)

  def get_agent_information(
      self,
      agent: str,
  ) -> list[dict[str, Any]]:

    department = self._agent_departments.get(agent)

    agent_information = []

    for info in self._state["all_information"].values():
      if info["department"] == None or info["department"] == department:
        agent_information.append(info)

    return agent_information

  def get_gm_information(self) -> list[dict[str, Any]]:
    return self._state["all_information"]

  def get_state(self) -> entity_component.ComponentState:
    return {"state": self._state}

  def set_state(
      self,
      state: entity_component.ComponentState,
  ) -> None:
    self._state = cast(dict[str, Any], state["state"])
