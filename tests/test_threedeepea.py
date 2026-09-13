import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from threedeepea import estimate_cost, load_config, parse_hhmmss

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "threedeepea.py"


class ParseHHMMSSTests(unittest.TestCase):
    def test_valid_values_are_converted_to_seconds(self):
        self.assertAlmostEqual(parse_hhmmss("00:00:00"), 0.0, places=9)
        self.assertAlmostEqual(parse_hhmmss("02:20:00"), 8400.0, places=9)
        self.assertAlmostEqual(parse_hhmmss("00:01:30"), 90.0, places=9)
        self.assertAlmostEqual(parse_hhmmss("99:59:59"), 359999.0, places=9)

    def test_single_digit_field_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("2:20:00")

    def test_decimal_field_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("02:20:00.5")

    def test_missing_field_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("02:20")

    def test_wrong_separator_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("02-20-00")

    def test_hours_over_ninety_nine_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("100:00:00")

    def test_minutes_of_sixty_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("02:60:00")

    def test_seconds_of_sixty_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("02:00:60")

    def test_non_numeric_text_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("notatime")

    def test_negative_value_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hhmmss("-1:00:00")


class CostEstimatorTests(unittest.TestCase):
    def test_average_model_includes_tiers_fees_and_repeats(self):
        config = {
            "filament_cost_per_kg": 24.0,
            "cost_model": "average",
            "repeats": 2,
            "report_level": "summary",
            "electricity": {
                "tier1_kwh": 100.0,
                "tier1_rate_per_kwh": 0.10,
                "tier2_rate_per_kwh": 0.20,
                "fees_per_kwh": [0.03, -0.01],
                "typical_monthly_kwh": 150.0,
            },
            "printer": {
                "warmup_minutes": 10.0,
                "warmup_watts": 300.0,
                "printing_watts": 120.0,
            },
        }

        result = estimate_cost(50.0, 1800.0, config)

        # Effective rate: ((100*0.1 + 50*0.2) + 150*0.02) / 150 = 0.153333...
        self.assertAlmostEqual(result["rate_details"]["effective_rate_per_kwh"], 23.0 / 150.0, places=9)
        self.assertAlmostEqual(result["filament_cost_total"], 2.4, places=9)
        self.assertAlmostEqual(result["warmup_kwh_total"], 0.1, places=9)
        self.assertAlmostEqual(result["printing_kwh_total"], 0.12, places=9)
        self.assertAlmostEqual(result["total_cost"], 2.4337333333333335, places=9)

    def test_invalid_cost_model_is_rejected(self):
        config = {
            "filament_cost_per_kg": 1.0,
            "cost_model": "invalid-model",
            "repeats": 1,
            "report_level": "summary",
            "electricity": {
                "tier1_kwh": 1.0,
                "tier1_rate_per_kwh": 0.1,
                "tier2_rate_per_kwh": 0.2,
                "fees_per_kwh": [0.01],
                "typical_monthly_kwh": 1.0,
            },
            "printer": {
                "warmup_minutes": 0.0,
                "warmup_watts": 0.0,
                "printing_watts": 0.0,
            },
        }
        with self.assertRaises(ValueError):
            estimate_cost(1.0, 60.0, config)

    def test_invalid_fee_entry_is_rejected(self):
        config = {
            "filament_cost_per_kg": 1.0,
            "cost_model": "average",
            "repeats": 1,
            "report_level": "summary",
            "electricity": {
                "tier1_kwh": 1.0,
                "tier1_rate_per_kwh": 0.1,
                "tier2_rate_per_kwh": 0.2,
                "fees_per_kwh": [0.01, "invalid"],
                "typical_monthly_kwh": 1.0,
            },
            "printer": {
                "warmup_minutes": 0.0,
                "warmup_watts": 0.0,
                "printing_watts": 0.0,
            },
        }
        with self.assertRaises(ValueError):
            estimate_cost(1.0, 60.0, config)

    def test_negative_print_time_is_rejected(self):
        config = {
            "filament_cost_per_kg": 1.0,
            "cost_model": "average",
            "repeats": 1,
            "report_level": "summary",
            "electricity": {
                "tier1_kwh": 1.0,
                "tier1_rate_per_kwh": 0.1,
                "tier2_rate_per_kwh": 0.2,
                "fees_per_kwh": [0.01],
                "typical_monthly_kwh": 1.0,
            },
            "printer": {
                "warmup_minutes": 0.0,
                "warmup_watts": 0.0,
                "printing_watts": 0.0,
            },
        }
        with self.assertRaises(ValueError):
            estimate_cost(1.0, -1.0, config)

    def test_load_config_rejects_directory_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                load_config(Path(tmpdir))

    def test_tier2_model_uses_tier2_plus_fees(self):
        config = {
            "filament_cost_per_kg": 20.0,
            "cost_model": "tier2",
            "repeats": 1,
            "report_level": "summary",
            "electricity": {
                "tier1_kwh": 0.0,
                "tier1_rate_per_kwh": 0.0,
                "tier2_rate_per_kwh": 0.30,
                "fees_per_kwh": [0.05],
                "typical_monthly_kwh": 0.0,
            },
            "printer": {
                "warmup_minutes": 1.0,
                "warmup_watts": 600.0,
                "printing_watts": 60.0,
            },
        }

        result = estimate_cost(100.0, 600.0, config)

        self.assertAlmostEqual(result["rate_details"]["effective_rate_per_kwh"], 0.35, places=9)
        self.assertAlmostEqual(result["electric_cost_total"], 0.007, places=9)

    def test_nan_print_time_is_rejected(self):
        config = {
            "filament_cost_per_kg": 1.0,
            "cost_model": "average",
            "repeats": 1,
            "report_level": "summary",
            "electricity": {
                "tier1_kwh": 1.0,
                "tier1_rate_per_kwh": 0.1,
                "tier2_rate_per_kwh": 0.2,
                "fees_per_kwh": [0.01],
                "typical_monthly_kwh": 1.0,
            },
            "printer": {
                "warmup_minutes": 0.0,
                "warmup_watts": 0.0,
                "printing_watts": 0.0,
            },
        }
        with self.assertRaises(ValueError):
            estimate_cost(1.0, float("nan"), config)


class CLITests(unittest.TestCase):
    def test_cli_rejects_missing_two_digit_fields(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "50", "--print-time", "2:20:00"],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("HH:MM:SS", completed.stderr)

    def test_cli_rejects_out_of_range_minutes(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "50", "--print-time", "02:60:00"],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_cli_overrides_cost_model_and_fees(self):
        config = {
            "report_level": "summary",
            "filament_cost_per_kg": 0.0,
            "cost_model": "average",
            "repeats": 1,
            "electricity": {
                "tier1_kwh": 100.0,
                "tier1_rate_per_kwh": 0.10,
                "tier2_rate_per_kwh": 0.20,
                "fees_per_kwh": [0.01],
                "typical_monthly_kwh": 100.0,
            },
            "printer": {
                "warmup_minutes": 60.0,
                "warmup_watts": 1000.0,
                "printing_watts": 0.0,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "cfg.json"
            cfg_path.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "0",
                    "--config",
                    str(cfg_path),
                    "--print-time",
                    "00:00:00",
                    "--cost-model",
                    "tier2",
                    "--fee-per-kwh",
                    "0.05",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        self.assertIn("Electricity: $0.2500", completed.stdout)

    def test_cli_electricity_model_alias_overrides_config(self):
        config = {
            "report_level": "summary",
            "filament_cost_per_kg": 0.0,
            "cost_model": "average",
            "repeats": 1,
            "electricity": {
                "tier1_kwh": 100.0,
                "tier1_rate_per_kwh": 0.10,
                "tier2_rate_per_kwh": 0.20,
                "fees_per_kwh": [0.01],
                "typical_monthly_kwh": 100.0,
            },
            "printer": {
                "warmup_minutes": 60.0,
                "warmup_watts": 1000.0,
                "printing_watts": 0.0,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "cfg.json"
            cfg_path.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "0",
                    "--config",
                    str(cfg_path),
                    "--print-time",
                    "00:00:00",
                    "--electricity-model",
                    "tier2",
                    "--fee-per-kwh",
                    "0.05",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        self.assertIn("Electricity: $0.2500", completed.stdout)

    def test_cli_verbose_contains_configuration_and_details(self):
        config = {
            "report_level": "verbose",
            "filament_cost_per_kg": 10.0,
            "cost_model": "average",
            "repeats": 1,
            "electricity": {
                "tier1_kwh": 500.0,
                "tier1_rate_per_kwh": 0.10,
                "tier2_rate_per_kwh": 0.20,
                "fees_per_kwh": [0.01],
                "typical_monthly_kwh": 600.0,
            },
            "printer": {
                "warmup_minutes": 1.0,
                "warmup_watts": 120.0,
                "printing_watts": 60.0,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "cfg.json"
            cfg_path.write_text(json.dumps(config), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "50",
                    "--config",
                    str(cfg_path),
                    "--print-time",
                    "00:01:00",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        output = completed.stdout
        self.assertIn("Resolved configuration:", output)
        self.assertIn("Calculation details:", output)
        self.assertIn("Warm-up kWh per plate:", output)

    def test_cli_standard_report_includes_subtotals_not_verbose_sections(self):
        config = {
            "report_level": "standard",
            "filament_cost_per_kg": 10.0,
            "cost_model": "average",
            "repeats": 1,
            "electricity": {
                "tier1_kwh": 100.0,
                "tier1_rate_per_kwh": 0.10,
                "tier2_rate_per_kwh": 0.20,
                "fees_per_kwh": [0.01],
                "typical_monthly_kwh": 100.0,
            },
            "printer": {
                "warmup_minutes": 1.0,
                "warmup_watts": 120.0,
                "printing_watts": 60.0,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "cfg.json"
            cfg_path.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "50",
                    "--config",
                    str(cfg_path),
                    "--print-time",
                    "00:05:00",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        output = completed.stdout
        self.assertIn("Warm-up electricity:", output)
        self.assertIn("Printing electricity:", output)
        self.assertNotIn("Resolved configuration:", output)
        self.assertNotIn("Calculation details:", output)

    def test_cli_warmup_electricity_is_visible_at_four_decimals(self):
        """Regression test: a small warm-up electricity cost used to round to
        $0.00 with 2-decimal formatting, making warm-up look free."""
        config = {
            "report_level": "standard",
            "filament_cost_per_kg": 0.0,
            "cost_model": "tier2",
            "repeats": 1,
            "electricity": {
                "tier1_kwh": 0.0,
                "tier1_rate_per_kwh": 0.0,
                "tier2_rate_per_kwh": 0.20,
                "fees_per_kwh": [0.05],
                "typical_monthly_kwh": 0.0,
            },
            "printer": {
                "warmup_minutes": 6.0,
                "warmup_watts": 100.0,
                "printing_watts": 0.0,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "cfg.json"
            cfg_path.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "0",
                    "--config",
                    str(cfg_path),
                    "--print-time",
                    "00:00:00",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        output = completed.stdout
        self.assertIn("Warm-up electricity: $0.0025", output)
        self.assertNotIn("Warm-up electricity: $0.00\n", output)


if __name__ == "__main__":
    unittest.main()
