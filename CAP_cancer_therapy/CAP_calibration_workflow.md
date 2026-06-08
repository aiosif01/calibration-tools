# CAP Calibration Guide

This guide merges the previous workflow note and data-integration report for the CAP in vitro calibration example.

It documents the current simplified model, the calibration inputs, the make-based workflow, and the current optimization strategy.

## Scope

- **Cell line**: `EGI1`
- **CAP duration**: `5 min`
- **Observed trajectory**: `0 h`, `24 h`, `48 h`, `72 h`
- **Base simulation input**: `input_inVitro.csv`
- **Calibration template**: `input_inVitro_calibration.csv`
- **ABM initial population in calibration template**: `30000`
- **Optimizers**: `differential_evolution`, `dual_annealing`, `nelder_mead`

## Biological interpretation of the current simplified model

The current CAP scenario represents a 3D tumor spheroid exposed to CAP-derived extracellular species:

- `H2O2` as a primary CAP-associated species
- `NO2_` as a secondary CAP-associated species
- `O2` as a baseline metabolic field for growth and survival rules

The current simplified in vitro model intentionally removes the more complicated extracellular dependency logic:

- no migration
- no chemotaxis
- no extracellular `H2O2` / `NO2_` secretion terms for cancer cells
- no RONS-controlled apoptosis, growth, or division dependencies
- CAP species act mainly through intracellular uptake, oxidative stress, and DNA damage

This makes the dominant mechanism:

- extracellular CAP exposure
- intracellular uptake of `H2O2` and `NO2_`
- intracellular oxidative stress accumulation
- DNA damage accumulation and delayed death / growth suppression
