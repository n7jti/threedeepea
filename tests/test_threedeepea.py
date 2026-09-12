import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from threedeepea import estimate_cost


class CostEstimatorTests(unittest.TestCase):
    def test_average_model_includes_tiers_fees_and_repeats(self):
        config = {
            "print_time_minutes": 30.0,
            "print_time_seconds": 0.0,
            "filament_cost_per_kg": 24.0,
            "average_cost_per_kwh": None,
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
                "warmup_seconds": 0.0,
                "warmup_watts": 300.0,
                "printing_watts": 120.0,
            },
        }

        result = estimate_cost(50.0, config)

        # Effective rate: ((100*0.1 + 50*0.2) + 150*0.02) / 150 = 0.153333...
        self.assertAlmostEqual(result["rate_details"]["effective_rate_per_kwh"], 23.0 / 150.0, places=9)
        self.assertAlmostEqual(result["filament_cost_total"], 2.4, places=9)
        self.assertAlmostEqual(result["warmup_kwh_total"], 0.1, places=9)
        self.assertAlmostEqual(result["printing_kwh_total"], 0.12, places=9)
        self.assertAlmostEqual(result["total_cost"], 2.4337333333333335, places=9)

    def test_tier2_model_uses_tier2_plus_fees(self):
        config = {
            "print_time_minutes": 10.0,
            "print_time_seconds": 0.0,
            "filament_cost_per_kg": 20.0,
            "average_cost_per_kwh": None,
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
                "warmup_minutes": 0.0,
                "warmup_seconds": 60.0,
                "warmup_watts": 600.0,
                "printing_watts": 60.0,
            },
        }

        result = estimate_cost(100.0, config)

        self.assertAlmostEqual(result["rate_details"]["effective_rate_per_kwh"], 0.35, places=9)
        self.assertAlmostEqual(result["electric_cost_total"], 0.007, places=9)

    def test_average_cost_override_adds_configured_fees(self):
        config = {
            "print_time_minutes": 60.0,
            "print_time_seconds": 0.0,
            "filament_cost_per_kg": 0.0,
            "average_cost_per_kwh": 0.20,
            "cost_model": "average",
            "repeats": 1,
            "report_level": "summary",
            "electricity": {
                "tier1_kwh": 100.0,
                "tier1_rate_per_kwh": 0.10,
                "tier2_rate_per_kwh": 0.50,
                "fees_per_kwh": [0.03, -0.01],
                "typical_monthly_kwh": 500.0,
            },
            "printer": {
                "warmup_minutes": 0.0,
                "warmup_seconds": 0.0,
                "warmup_watts": 0.0,
                "printing_watts": 1000.0,
            },
        }
        result = estimate_cost(0.0, config)
        self.assertAlmostEqual(result["rate_details"]["tier_only_rate_per_kwh"], 0.20, places=9)
        self.assertAlmostEqual(result["rate_details"]["effective_rate_per_kwh"], 0.22, places=9)
        self.assertAlmostEqual(result["electric_cost_total"], 0.22, places=9)

    def test_cli_overrides_cost_model_and_fees(self):
        config = {
            "report_level": "summary",
            "print_time_minutes": 0.0,
            "print_time_seconds": 0.0,
            "filament_cost_per_kg": 0.0,
            "average_cost_per_kwh": None,
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
                "warmup_seconds": 0.0,
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
                    "-m",
                    "threedeepea",
                    "0",
                    "--config",
                    str(cfg_path),
                    "--cost-model",
                    "tier2",
                    "--fee-per-kwh",
                    "0.05",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        self.assertIn("Electricity: $0.25", completed.stdout)

    def test_cli_verbose_contains_configuration_and_details(self):
        config = {
            "report_level": "verbose",
            "print_time_minutes": 1.0,
            "print_time_seconds": 0.0,
            "filament_cost_per_kg": 10.0,
            "average_cost_per_kwh": 0.20,
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
                "warmup_seconds": 30.0,
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
                    "-m",
                    "threedeepea",
                    "50",
                    "--config",
                    str(cfg_path),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        output = completed.stdout
        self.assertIn("Resolved configuration:", output)
        self.assertIn("Calculation details:", output)
        self.assertIn("Warm-up kWh per plate:", output)


if __name__ == "__main__":
    unittest.main()
