from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
MODULE_DIR = CURRENT_DIR.parent
REPO_ROOT = MODULE_DIR.parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from judge_model import JudgeModel
from model_router import ModelRouter, load_llm_config
from models import SensorData, SystemState
from multi_llm_analyzer import MultiLLMAnalyzer
from output_writer import OutputWriter
from rule_engine import RuleEngine
from safety_guard import SafetyGuard
from task_classifier import TaskClassifier


DEFAULT_INPUT = {
    "device_id": "device_001",
    "temperature": 72.5,
    "humidity": 61.0,
    "gas": 0.25,
    "vibration": 1.82,
    "current": 2.3,
    "cloud_connected": True,
    "voice_state": "idle",
    "sensor_online": True,
}


def run_demo(input_data: dict, force_model: str = "") -> dict:
    thresholds_path = MODULE_DIR / "config" / "thresholds.json"
    llm_config_path = MODULE_DIR / "config" / "llm_config.yaml"
    output_path = MODULE_DIR / "runtime" / "system_status.json"

    sensor_data = SensorData.from_dict(input_data)
    system_state = SystemState.from_dict(input_data)

    rule_engine = RuleEngine.from_file(thresholds_path)
    rule_result = rule_engine.evaluate(sensor_data, system_state)

    task_type = TaskClassifier().classify(rule_result, system_state)
    llm_config = load_llm_config(llm_config_path)
    router_decision = ModelRouter(llm_config).route(
        task_type=task_type,
        rule_result=rule_result,
        network_state=system_state.cloud_connected,
        force_model=force_model,
    )

    model_results = MultiLLMAnalyzer(llm_config).analyze(
        sensor_data=sensor_data,
        system_state=system_state,
        rule_result=rule_result,
        selected_models=router_decision.selected_models,
    )
    judge_result = JudgeModel().judge(sensor_data, system_state, rule_result, model_results)
    analysis_mode = _analysis_mode(router_decision.selected_models, model_results)
    final_status = SafetyGuard().enforce(
        judge_result=judge_result,
        rule_result=rule_result,
        sensor_data=sensor_data,
        system_state=system_state,
        llm_available=bool(router_decision.selected_models),
        analysis_mode=analysis_mode,
    )
    OutputWriter(output_path).write(final_status)

    result = final_status.to_dict()
    result["_debug"] = {
        "task_type": task_type,
        "router": router_decision.to_dict(),
        "rule_result": rule_result.to_dict(),
        "model_results": [item.to_dict() for item in model_results],
        "judge_result": judge_result.to_dict(),
    }
    return result


def _analysis_mode(selected_models: list[str], model_results: list) -> str:
    if not selected_models:
        return "rule_fallback"
    has_real_success = any(
        item.error is None and item.model_name not in ("mock", "rule_fallback") and not item.model_name.endswith("_mock")
        for item in model_results
    )
    return "real_multi_llm" if has_real_success else "mock_multi_llm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyzer module demo")
    parser.add_argument("--input-json", help="Inline JSON input for sensor/system state.")
    parser.add_argument("--input-file", help="Path to JSON input file.")
    parser.add_argument("--use-real-llm", action="store_true", help="Enable real cloud LLM API calls.")
    parser.add_argument(
        "--force-model",
        choices=["deepseek", "kimi", "zhipu", "doubao", "qwen", "mock"],
        default="",
        help="Force one model for step-by-step API debugging.",
    )
    parser.add_argument("--print-debug", action="store_true", help="Print router and model debug details.")
    return parser.parse_args()


def load_input(args: argparse.Namespace) -> dict:
    if args.input_json:
        return json.loads(args.input_json)
    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as file:
            return json.load(file)
    return dict(DEFAULT_INPUT)


def main() -> None:
    args = parse_args()
    if args.use_real_llm:
        os.environ["ANALYZER_USE_REAL_LLM"] = "true"

    result = run_demo(load_input(args), force_model=args.force_model)
    output = result if args.print_debug else {key: value for key, value in result.items() if key != "_debug"}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print("分析完成，结果已写入 modules/analyzer/runtime/system_status.json")


if __name__ == "__main__":
    main()
