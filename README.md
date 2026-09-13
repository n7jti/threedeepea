# threedeepea

Command line Python tool for estimating 3D print cost.

## Usage

```bash
python threedeepea.py WEIGHT_GRAMS --print-time-minutes MINUTES [options]
```

Required inputs:
- `WEIGHT_GRAMS`: filament mass for one print job (a complete print tray with a single warm-up phase).
- `--print-time-minutes`: print time in minutes.

Optional inputs are read from `threedeepea_config.json` and can all be overridden via CLI flags:
- filament cost (`--filament-cost-per-kg`)
- electricity cost model (`--cost-model average|tier2` or `--electricity-model average|tier2`)
- repeats (`--repeats`): the number of times the print tray will be repeated. Cost of a single tray is multiplied by this number to get the total cost of the print run.
- report level (`--report-level summary|standard|verbose`)
- tier and fee settings (`--tier1-kwh`, `--tier1-rate-per-kwh`, `--tier2-rate-per-kwh`, `--fee-per-kwh`, `--typical-monthly-kwh`)
- printer model (`--warmup-minutes`, `--warmup-watts`, `--printing-watts`)

## Reporting levels

- `summary` (default): cost per plate plus filament and electricity totals.
- `standard`: summary + warm-up and printing electricity subtotals.
- `verbose`: standard + resolved configuration + intermediate calculations.

If you provide one or more `--fee-per-kwh` flags, they replace the config file's `fees_per_kwh` list.
Fee values can be positive or negative, matching bills that include credits or surcharges.

## Electricity Cost Models

### "average" model
Calculates an effective average rate based on typical monthly usage. The effective rate accounts for:
- Tier 1 kWh consumption up to the tier limit
- Tier 2 kWh consumption above the tier limit
- All per-kWh fees (positive or negative)

### "tier2" model
Assumes all print electricity is consumed at the marginal Tier 2 rate, plus all fees.
