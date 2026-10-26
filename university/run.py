import argparse
import importlib
import sys
import json
import datetime

from university import simulation
from university.language_models.mlx_model import MlxModel
from pathlib import Path
from collections import Counter
from university.components.university_state import STATUS_OPTIONS
from typing import get_args
import sentence_transformers

_DEFAULT_SCENARIOS = {
    "university": "semester",
}

# Similarily to examples\games\run.py
def main() -> None:
  parser = argparse.ArgumentParser(
      description="Run the university simulation.",
  )
  parser.add_argument(
      "--scenario",
      type=str,
      default=_DEFAULT_SCENARIOS["university"],
  )
  parser.add_argument(
      "--model_name",
      type=str,
      default="mlx-community/Qwen3.6-27B-8bit",
      help="Name of the language model to use.",
  )
  parser.add_argument(
      "--base_url",
      type=str,
      default=None,
      help="Base URL for the language model.",
  )
  parser.add_argument(
      "--api_key",
      type=str,
      default=None,
      help="API key for the language model provider.",
  )
  parser.add_argument(
      "--disable_language_model",
      action="store_true",
      help="Run with a mock language model (for testing).",
  )

  parser.add_argument(
      "--debug_log",
      action="store_true",
      help="Write full Concordia HTML and JSON logs.",
  )

  args = parser.parse_args()

  scenario = args.scenario or _DEFAULT_SCENARIOS["university"]

  config_path = f"university.config.{scenario}"
  try:
      config = importlib.import_module(config_path)
  except ImportError as e:
      print(
        f"Could not load scenario '{scenario}': {e}",
        file=sys.stderr,
      )
      sys.exit(1)

  model = MlxModel(
    model_name=args.model_name,
    base_url=args.base_url,
  )

  st_model = sentence_transformers.SentenceTransformer("all-mpnet-base-v2")
  embedder = lambda x: st_model.encode(x, show_progress_bar=False)

  print(f"Starting university simulation with scenario: {scenario}...")
  results = simulation.run_simulation(
      config=config,
      model=model,
      embedder=embedder,
  )

  print("Simulation finished.")

  # Create a summary of all the final states.
  summary = {
    "scenario": scenario,
    "university_state": results["university_state"].get_state()["state"],
    "relationship_states": results["relationship_states"].get_state()["state"],
    "communication_state": results["communication_state"].get_state()["state"],
    "planning_state": results["planning_state"].get_state()["state"],
    "agents": results["agents"],
  }

  university_events = summary["university_state"].get("events", [])
  event_counter = Counter(event["status"] for event in university_events)

  relationship_updates = summary["relationship_states"].get("history", [])
  update_counter = Counter(update["status"] for update in relationship_updates)

  messages = summary["communication_state"].get("messages", [])
  message_counter = Counter(message["status"] for message in messages)

  weekly_plans = summary["planning_state"].get("history", [])
  plan_counter = Counter(plan["status"] for plan in weekly_plans)

  summary["administration_action_counter"] = {}
  summary["relationship_update_counter"] = {}
  summary["message_counter"] = {}
  summary["weekly_plan_counter"] = {}

  for status in get_args(STATUS_OPTIONS):
    summary["administration_action_counter"][status] = event_counter[status]
    summary["relationship_update_counter"][status] = update_counter[status]
    summary["message_counter"][status] = message_counter[status]
    summary["weekly_plan_counter"][status] = plan_counter[status]

  # Write output files
  if results and "structured_log" in results:
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path("simulation_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.debug_log:
      structured_log = results["structured_log"]

      html_file = output_dir / f"simulation_debug_university_{scenario}_{run_id}.html"
      with open(html_file, "w") as f:
        f.write(structured_log.to_html())
      print(f"HTML results written to {html_file}")

      json_file = output_dir / f"simulation_debug_university_{scenario}_{run_id}.json"
      with open(json_file, "w") as f:
        f.write(structured_log.to_json())
      print(f"JSON log written to {json_file}")

    summary_file = output_dir / f"simulation_summary_university_{scenario}_{run_id}.json"
    with open(summary_file, "w") as f:
      json.dump(summary, f, indent=2)
    print(f"Summary written to {summary_file}")

if __name__ == "__main__":
  main()
