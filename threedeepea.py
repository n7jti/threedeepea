import argparse
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_CONFIG: Dict[str, Any] = {
    "print_time_minutes": 60.0,
    "print_time_seconds": 0.0,
    "filament_cost_per_kg": 20.0,
    "average_cost_per_kwh": None,
    "cost_model": "average",
    "repeats": 1,
    "report_level": "summary",
    "electricity": {
        "tier1_kwh": 500.0,
        "tier1_rate_per_kwh": 0.20,
        "tier2_rate_per_kwh": 0.35,
        "fees_per_kwh": [0.03],
        "typical_monthly_kwh": 600.0,
    },
    "printer": {
        "warmup_minutes": 5.0,
        "warmup_seconds": 0.0,
        "warmup_watts": 220.0,
        "printing_watts": 120.0,
    },
}


def load_config(path: Path) -> Dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if path.exists():
        if not path.is_file():
            raise ValueError(f"Config path is not a file: {path}")
        with path.open("r", encoding="utf-8") as handle:
            user_config = json.load(handle)
        merge_dicts(config, user_config)
    return config


def merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_dicts(base[key], value)
        else:
            base[key] = value


def apply_overrides(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    cfg = deepcopy(config)

    scalar_overrides = {
        "print_time_minutes": args.print_time_minutes,
        "print_time_seconds": args.print_time_seconds,
        "filament_cost_per_kg": args.filament_cost_per_kg,
        "average_cost_per_kwh": args.average_cost_per_kwh,
        "cost_model": args.cost_model,
        "repeats": args.repeats,
        "report_level": args.report_level,
    }
    for key, value in scalar_overrides.items():
        if value is not None:
            cfg[key] = value

    electricity_overrides = {
        "tier1_kwh": args.tier1_kwh,
        "tier1_rate_per_kwh": args.tier1_rate_per_kwh,
        "tier2_rate_per_kwh": args.tier2_rate_per_kwh,
        "typical_monthly_kwh": args.typical_monthly_kwh,
    }
    for key, value in electricity_overrides.items():
        if value is not None:
            cfg["electricity"][key] = value
    if args.fee_per_kwh is not None:
        cfg["electricity"]["fees_per_kwh"] = args.fee_per_kwh

    printer_overrides = {
        "warmup_minutes": args.warmup_minutes,
        "warmup_seconds": args.warmup_seconds,
        "warmup_watts": args.warmup_watts,
        "printing_watts": args.printing_watts,
    }
    for key, value in printer_overrides.items():
        if value is not None:
            cfg["printer"][key] = value

    return cfg


def validate_inputs(weight_grams: float, config: Dict[str, Any]) -> None:
    def finite_number(name: str, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be numeric") from None
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        return number

    weight_grams = finite_number("weight_grams", weight_grams)
    if weight_grams < 0:
        raise ValueError("weight_grams must be non-negative")
    if config["cost_model"] not in {"average", "tier2"}:
        raise ValueError("cost_model must be one of: average, tier2")
    if config["report_level"] not in {"summary", "standard", "verbose"}:
        raise ValueError("report_level must be one of: summary, standard, verbose")
    repeats_numeric = finite_number("repeats", config["repeats"])
    if not repeats_numeric.is_integer():
        raise ValueError("repeats must be an integer value")
    if repeats_numeric <= 0:
        raise ValueError("repeats must be greater than 0")
    print_time_minutes = finite_number("print_time_minutes", config["print_time_minutes"])
    print_time_seconds = finite_number("print_time_seconds", config.get("print_time_seconds", 0.0))
    if print_time_minutes < 0 or print_time_seconds < 0:
        raise ValueError("print time values must be non-negative")
    if print_time_seconds >= 60:
        raise ValueError("print_time_seconds must be less than 60")
    if finite_number("filament_cost_per_kg", config["filament_cost_per_kg"]) < 0:
        raise ValueError("filament_cost_per_kg must be non-negative")
    if config.get("average_cost_per_kwh") is not None and finite_number("average_cost_per_kwh", config["average_cost_per_kwh"]) < 0:
        raise ValueError("average_cost_per_kwh must be non-negative when provided")

    electricity = config["electricity"]
    if finite_number("electricity.tier1_kwh", electricity["tier1_kwh"]) < 0:
        raise ValueError("electricity.tier1_kwh must be non-negative")
    if finite_number("electricity.tier1_rate_per_kwh", electricity["tier1_rate_per_kwh"]) < 0:
        raise ValueError("electricity.tier1_rate_per_kwh must be non-negative")
    if finite_number("electricity.tier2_rate_per_kwh", electricity["tier2_rate_per_kwh"]) < 0:
        raise ValueError("electricity.tier2_rate_per_kwh must be non-negative")
    if finite_number("electricity.typical_monthly_kwh", electricity["typical_monthly_kwh"]) < 0:
        raise ValueError("electricity.typical_monthly_kwh must be non-negative")
    fees = electricity.get("fees_per_kwh")
    if not isinstance(fees, list):
        raise ValueError("electricity.fees_per_kwh must be a list")
    for fee in fees:
        finite_number("electricity.fees_per_kwh entry", fee)

    printer = config["printer"]
    warmup_minutes = finite_number("printer.warmup_minutes", printer["warmup_minutes"])
    warmup_seconds = finite_number("printer.warmup_seconds", printer["warmup_seconds"])
    if warmup_minutes < 0 or warmup_seconds < 0:
        raise ValueError("printer warm-up time values must be non-negative")
    if warmup_seconds >= 60:
        raise ValueError("printer.warmup_seconds must be less than 60")
    if finite_number("printer.warmup_watts", printer["warmup_watts"]) < 0:
        raise ValueError("printer.warmup_watts must be non-negative")
    if finite_number("printer.printing_watts", printer["printing_watts"]) < 0:
        raise ValueError("printer.printing_watts must be non-negative")


def compute_effective_rate(config: Dict[str, Any]) -> Dict[str, float]:
    electricity = config["electricity"]
    fees_per_kwh_total = sum(float(fee) for fee in electricity["fees_per_kwh"])

    if config["cost_model"] == "tier2":
        tier_only_rate = float(electricity["tier2_rate_per_kwh"])
        return {
            "effective_rate_per_kwh": tier_only_rate + fees_per_kwh_total,
            "tier_only_rate_per_kwh": tier_only_rate,
            "fees_per_kwh_total": fees_per_kwh_total,
            "monthly_energy_cost": 0.0,
            "monthly_total_cost": 0.0,
            "monthly_usage_kwh": 0.0,
            "tier1_usage_kwh": 0.0,
            "tier2_usage_kwh": 0.0,
        }

    if config["cost_model"] == "average" and config.get("average_cost_per_kwh") is not None:
        tier_only_rate = float(config["average_cost_per_kwh"])
        return {
            "effective_rate_per_kwh": tier_only_rate + fees_per_kwh_total,
            "tier_only_rate_per_kwh": tier_only_rate,
            "fees_per_kwh_total": fees_per_kwh_total,
            "monthly_energy_cost": 0.0,
            "monthly_total_cost": 0.0,
            "monthly_usage_kwh": 0.0,
            "tier1_usage_kwh": 0.0,
            "tier2_usage_kwh": 0.0,
        }

    usage = float(electricity["typical_monthly_kwh"])
    tier1_limit = float(electricity["tier1_kwh"])
    tier1_usage = min(usage, tier1_limit)
    tier2_usage = max(usage - tier1_usage, 0.0)

    monthly_energy_cost = (
        tier1_usage * float(electricity["tier1_rate_per_kwh"])
        + tier2_usage * float(electricity["tier2_rate_per_kwh"])
    )
    monthly_total_cost = monthly_energy_cost + (usage * fees_per_kwh_total)
    if usage > 0:
        tier_only_rate = monthly_energy_cost / usage
        effective_rate = monthly_total_cost / usage
    else:
        tier_only_rate = float(electricity["tier1_rate_per_kwh"])
        effective_rate = tier_only_rate + fees_per_kwh_total

    return {
        "effective_rate_per_kwh": effective_rate,
        "tier_only_rate_per_kwh": tier_only_rate,
        "fees_per_kwh_total": fees_per_kwh_total,
        "monthly_energy_cost": monthly_energy_cost,
        "monthly_total_cost": monthly_total_cost,
        "monthly_usage_kwh": usage,
        "tier1_usage_kwh": tier1_usage,
        "tier2_usage_kwh": tier2_usage,
    }


def estimate_cost(weight_grams: float, config: Dict[str, Any]) -> Dict[str, Any]:
    validate_inputs(weight_grams, config)

    repeats = int(float(config["repeats"]))
    print_seconds = float(config["print_time_minutes"]) * 60.0 + float(config.get("print_time_seconds", 0.0))
    warmup_seconds = float(config["printer"]["warmup_minutes"]) * 60.0 + float(config["printer"]["warmup_seconds"])

    filament_cost_total = (weight_grams / 1000.0) * float(config["filament_cost_per_kg"]) * repeats

    warmup_kwh_single = (warmup_seconds / 3600.0) * (float(config["printer"]["warmup_watts"]) / 1000.0)
    printing_kwh_single = (print_seconds / 3600.0) * (float(config["printer"]["printing_watts"]) / 1000.0)

    warmup_kwh_total = warmup_kwh_single * repeats
    printing_kwh_total = printing_kwh_single * repeats

    rate_details = compute_effective_rate(config)
    effective_rate = rate_details["effective_rate_per_kwh"]

    warmup_electric_cost = warmup_kwh_total * effective_rate
    printing_electric_cost = printing_kwh_total * effective_rate
    electric_cost_total = warmup_electric_cost + printing_electric_cost

    total_cost = filament_cost_total + electric_cost_total
    cost_per_plate = total_cost / repeats

    return {
        "weight_grams": weight_grams,
        "repeats": repeats,
        "print_seconds": print_seconds,
        "warmup_seconds": warmup_seconds,
        "filament_cost_total": filament_cost_total,
        "warmup_kwh_single": warmup_kwh_single,
        "printing_kwh_single": printing_kwh_single,
        "warmup_kwh_total": warmup_kwh_total,
        "printing_kwh_total": printing_kwh_total,
        "warmup_electric_cost": warmup_electric_cost,
        "printing_electric_cost": printing_electric_cost,
        "electric_cost_total": electric_cost_total,
        "total_cost": total_cost,
        "cost_per_plate": cost_per_plate,
        "rate_details": rate_details,
    }


def format_currency(value: float) -> str:
    return f"${value:.2f}"


def render_report(config: Dict[str, Any], result: Dict[str, Any]) -> str:
    lines: List[str] = []
    level = config["report_level"]

    lines.append(f"Cost per plate: {format_currency(result['cost_per_plate'])}")

    if level == "summary":
        lines.append(f"Filament: {format_currency(result['filament_cost_total'])}")
        lines.append(f"Electricity: {format_currency(result['electric_cost_total'])}")
        lines.append(f"Total job cost ({result['repeats']} prints): {format_currency(result['total_cost'])}")
        return "\n".join(lines)

    lines.append(f"Filament subtotal: {format_currency(result['filament_cost_total'])}")
    lines.append(f"Electricity subtotal: {format_currency(result['electric_cost_total'])}")
    lines.append(f"  Warm-up electricity: {format_currency(result['warmup_electric_cost'])}")
    lines.append(f"  Printing electricity: {format_currency(result['printing_electric_cost'])}")
    lines.append(f"Total job cost ({result['repeats']} prints): {format_currency(result['total_cost'])}")

    if level == "verbose":
        lines.append("")
        lines.append("Resolved configuration:")
        lines.append(json.dumps(config, indent=2, sort_keys=True))

        lines.append("")
        lines.append("Calculation details:")
        lines.append(f"Weight per plate (g): {result['weight_grams']:.4f}")
        lines.append(f"Repeats: {result['repeats']}")
        lines.append(f"Print time (s): {result['print_seconds']:.4f}")
        lines.append(f"Warm-up time (s): {result['warmup_seconds']:.4f}")
        lines.append(f"Warm-up kWh per plate: {result['warmup_kwh_single']:.8f}")
        lines.append(f"Printing kWh per plate: {result['printing_kwh_single']:.8f}")
        lines.append(f"Warm-up kWh total: {result['warmup_kwh_total']:.8f}")
        lines.append(f"Printing kWh total: {result['printing_kwh_total']:.8f}")
        lines.append(
            f"Effective electricity rate ($/kWh): {result['rate_details']['effective_rate_per_kwh']:.8f}"
        )
        lines.append(
            f"Tier-only electricity rate ($/kWh): {result['rate_details']['tier_only_rate_per_kwh']:.8f}"
        )
        lines.append(
            f"Fees total ($/kWh): {result['rate_details']['fees_per_kwh_total']:.8f}"
        )
        lines.append(
            f"Monthly usage for average model (kWh): {result['rate_details']['monthly_usage_kwh']:.4f}"
        )
        lines.append(
            f"Monthly tier-1 usage (kWh): {result['rate_details']['tier1_usage_kwh']:.4f}"
        )
        lines.append(
            f"Monthly tier-2 usage (kWh): {result['rate_details']['tier2_usage_kwh']:.4f}"
        )
        lines.append(
            f"Monthly energy-only cost ($): {result['rate_details']['monthly_energy_cost']:.4f}"
        )
        lines.append(
            f"Monthly total cost incl. fees ($): {result['rate_details']['monthly_total_cost']:.4f}"
        )

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Estimate 3D printing costs.")
    parser.add_argument("weight_grams", type=float, help="Filament weight required in grams.")

    parser.add_argument("--config", default="threedeepea_config.json", help="Path to JSON config file.")
    parser.add_argument("--print-time-minutes", type=float)
    parser.add_argument("--print-time-seconds", type=float)
    parser.add_argument("--filament-cost-per-kg", type=float)
    parser.add_argument("--average-cost-per-kwh", type=float)
    parser.add_argument("--cost-model", "--electricity-model", dest="cost_model", choices=["average", "tier2"])
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--report-level", choices=["summary", "standard", "verbose"])

    parser.add_argument("--tier1-kwh", type=float)
    parser.add_argument("--tier1-rate-per-kwh", type=float)
    parser.add_argument("--tier2-rate-per-kwh", type=float)
    parser.add_argument("--fee-per-kwh", type=float, action="append")
    parser.add_argument("--typical-monthly-kwh", type=float)

    parser.add_argument("--warmup-minutes", type=float)
    parser.add_argument("--warmup-seconds", type=float)
    parser.add_argument("--warmup-watts", type=float)
    parser.add_argument("--printing-watts", type=float)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        config_path = Path(args.config)
        config = load_config(config_path)
        config = apply_overrides(config, args)
        result = estimate_cost(args.weight_grams, config)
    except ValueError as error:
        parser.error(str(error))
        return

    print(render_report(config, result))


if __name__ == "__main__":
    main()
