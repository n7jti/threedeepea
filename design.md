# Design Document: 3D Print Cost Estimation Tool

## Overview
A command-line Python tool for estimating the cost of 3D printing, accounting for filament consumption, electricity usage with tiered billing, and repeated print runs.

## Requirements

### 1. Required Inputs
- **Filament weight (grams)**: The mass of filament needed for a single print job (one print tray, single warm-up phase).
- **Print time (minutes)**: Duration of the printing phase.

### 2. Optional Inputs (from config file or CLI overrides)
- **Filament cost ($/kg)**: Cost per kilogram of filament.
- **Cost model**: Choice of electricity billing model (`average` or `tier2`).
- **Repeats**: Number of times the print tray will be repeated. Total cost = single tray cost × repeats.
- **Report level**: Output verbosity (`summary`, `standard`, or `verbose`).
- **Printer parameters**: Warm-up duration, warm-up power draw, printing power draw.
- **Electricity parameters**: Tier 1 cap, tier rates, tier 2 rate, monthly fees, typical monthly usage.

### 3. Configuration File
Located at `threedeepea_config.json` (or custom path via `--config`). Provides defaults for all optional inputs. Print time is NOT in config—it must be provided via CLI.

### 4. Filament Cost Calculation
```
filament_cost_total = (weight_grams / 1000) × filament_cost_per_kg × repeats
```

### 5. Electricity Cost Model

#### 5.1 Electricity Parameters
- **tier1_kwh**: kWh cap for Tier 1 rate.
- **tier1_rate_per_kwh**: Price per kWh in Tier 1.
- **tier2_rate_per_kwh**: Price per kWh in Tier 2 (usage above Tier 1 cap).
- **fees_per_kwh**: List of per-kWh fees/surcharges (can be positive or negative).
- **typical_monthly_kwh**: Typical household/facility monthly usage (used only for `average` model).

#### 5.2 Cost Model: "average"
Used to calculate an effective average rate reflecting realistic household billing:
1. Calculate how many kWh fall into Tier 1 and Tier 2 based on `typical_monthly_kwh`:
   - tier1_usage = min(typical_monthly_kwh, tier1_kwh)
   - tier2_usage = max(typical_monthly_kwh - tier1_usage, 0)
2. Calculate total monthly tier cost (before fees):
   - monthly_tier_only_cost = (tier1_usage × tier1_rate_per_kwh) + (tier2_usage × tier2_rate_per_kwh)
3. Calculate total monthly fees cost:
   - monthly_fees_cost = typical_monthly_kwh × sum(fees_per_kwh)
4. Calculate total monthly cost including fees:
   - monthly_total_cost = monthly_tier_only_cost + monthly_fees_cost
5. Derive the effective per-kWh rates:
   - tier_only_rate = monthly_tier_only_cost / typical_monthly_kwh
   - effective_rate = monthly_total_cost / typical_monthly_kwh

#### 5.3 Cost Model: "tier2"
Assumes all print electricity is consumed at the marginal Tier 2 rate:
- tier_only_rate = tier2_rate_per_kwh
- effective_rate = tier2_rate_per_kwh + sum(fees_per_kwh)

#### 5.4 Printer Power Model
The printer has two phases:
- **Warm-up phase**: Fixed power draw (warmup_watts) for warmup duration → warmup_kwh
- **Printing phase**: Variable power draw (printing_watts) for print_time_minutes → printing_kwh

For a single plate:
- warmup_kwh_single = (warmup_minutes × 60 / 3600) × (warmup_watts / 1000)
- printing_kwh_single = (print_minutes × 60 / 3600) × (printing_watts / 1000)

For repeated runs:
- warmup_kwh_total = warmup_kwh_single × repeats
- printing_kwh_total = printing_kwh_single × repeats

Both phases use the effective electricity rate calculated above.

#### 5.5 Total Electricity Cost
```
warmup_electric_cost = warmup_kwh_total × effective_rate
printing_electric_cost = printing_kwh_total × effective_rate
electric_cost_total = warmup_electric_cost + printing_electric_cost
```

### 6. Total Cost Calculation
```
total_cost = filament_cost_total + electric_cost_total
cost_per_plate = total_cost / repeats
```

### 7. Reporting Modes

#### 7.1 Summary (default)
- Cost per plate
- Filament cost total
- Electricity cost total
- Total job cost (for all repeats)

#### 7.2 Standard
- Cost per plate
- Filament subtotal
- Electricity subtotal (broken into warm-up and printing components)
- Total job cost

#### 7.3 Verbose
- All of Standard
- Resolved configuration (formatted JSON)
- Detailed calculation trace:
  - Input parameters (weight, repeats, print time, warm-up time)
  - Per-plate energy usage (kWh)
  - Total energy usage (kWh)
  - Rate calculations (tier-only, effective, fees)
  - Monthly usage breakdown for average model (Tier 1 and Tier 2 usage)
  - Monthly cost details (tier-only, fees, total)

### 8. Validation
- Weight must be non-negative.
- Print time must be non-negative.
- Filament cost must be non-negative.
- Repeats must be a positive integer.
- Cost model must be one of: `average`, `tier2`.
- Report level must be one of: `summary`, `standard`, `verbose`.
- All electricity and printer parameters must be finite non-negative numbers.
- Warm-up time must be non-negative.
- Fees list must contain only numeric values.

### 9. Configuration Override Precedence
1. Defaults in code.
2. Config file (merged deeply to allow partial overrides).
3. CLI flags (applied individually for scalar values).

## Example Usage

```bash
# Basic usage with print time (required)
python threedeepea.py 85 --print-time-minutes 140

# With custom electricity model and fees
python threedeepea.py 85 \
  --print-time-minutes 140 \
  --electricity-model average \
  --fee-per-kwh 0.03 \
  --report-level standard

# Repeat run with verbose output
python threedeepea.py 85 \
  --print-time-minutes 140 \
  --repeats 5 \
  --report-level verbose
```
