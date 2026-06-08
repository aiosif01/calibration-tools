# CAP Calibration with Instantaneous Dose Scaling

> **ABM calibration update:** `calibrate_cap_viability_abm.py` now sets `CAP/duration_h` to the
> physical exposure length in hours (e.g. 15 s → `15/3600` h) and does **not** scale RONS
> concentrations by exposure ratio. Sub-minute exposures still overlap only part of the first
> `time_step` (0.01 h = 36 s); see `describe_cap_abm_timestep()` in the calibration log.

## Problem Statement

The ABM4bio model has a fundamental **timing resolution issue** that prevents realistic simulation of short CAP (cold atmospheric plasma) exposures:

- **Current time step**: `time_step = 0.01 h = 36 seconds`
- **CAP exposures to model**: 15 s, 30 s, 1 min, 2 min, 3 min, 4 min, 5 min
