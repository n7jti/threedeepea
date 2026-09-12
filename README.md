# threedeepea

Command line Python tool for estimating 3D print cost.

## Usage

```bash
python -m threedeepea WEIGHT_GRAMS [options]
```

Required input:
- `WEIGHT_GRAMS`: filament mass for one print.

Optional inputs are read from `threedeepea_config.json` and can all be overridden via CLI flags:
- print time (`--print-time-minutes`, `--print-time-seconds`)
- filament cost (`--filament-cost-per-kg`)
- average electricity override (`--average-cost-per-kwh`)
- electricity cost model (`--cost-model average|tier2`)
- repeats (`--repeats`)
- report level (`--report-level summary|standard|verbose`)
- tier and fee settings (`--tier1-kwh`, `--tier1-rate-per-kwh`, `--tier2-rate-per-kwh`, `--fee-per-kwh`, `--typical-monthly-kwh`)
- printer model (`--warmup-minutes`, `--warmup-seconds`, `--warmup-watts`, `--printing-watts`)

## Reporting levels

- `summary` (default): cost per plate plus filament and electricity totals.
- `standard`: summary + warm-up and printing electricity subtotals.
- `verbose`: standard + resolved configuration + intermediate calculations.
