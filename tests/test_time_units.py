"""Unit tests for ABM4bio hour ↔ step conversions and simulation clocks."""
from __future__ import annotations

import unittest
from pathlib import Path

from abmcal.time_units import (
    SimulationClock,
    hours_to_steps,
    minutes_to_time_step_h,
    read_template_simulation_hours,
    read_template_time_step_hours,
    seconds_to_steps,
    seconds_to_time_step_h,
    steps_to_hours,
    template_abm_value_to_optimizer_hours,
    validate_simulation_clock,
)
from config.calibration_settings import (
    CAP_EXPOSURE_SECONDS,
    mechanism11_simulation_clock,
    mechanism12_simulation_clock,
)

ROOT = Path(__file__).resolve().parents[1]
M11_TEMPLATE = ROOT / "templates" / "input_control_mechanism11_template.csv"
M12_TEMPLATE = ROOT / "templates" / "input_mechanism12_CAP_template.csv"


class TestTimeUnits(unittest.TestCase):
    def test_minute_and_second_time_step_h(self) -> None:
        self.assertAlmostEqual(minutes_to_time_step_h(1.0), 1.0 / 60.0)
        self.assertAlmostEqual(seconds_to_time_step_h(1.0), 1.0 / 3600.0)

    def test_control_clock_72h(self) -> None:
        clock = mechanism11_simulation_clock()
        self.assertEqual(clock.number_of_steps, 4320)
        self.assertAlmostEqual(clock.time_step_minutes, 1.0)
        self.assertAlmostEqual(steps_to_hours(clock.number_of_steps, clock.time_step_h), 72.0)

    def test_cap_clock_72h(self) -> None:
        clock = mechanism12_simulation_clock()
        self.assertEqual(clock.number_of_steps, 259200)
        self.assertAlmostEqual(clock.time_step_seconds, 1.0)
        self.assertAlmostEqual(steps_to_hours(clock.number_of_steps, clock.time_step_h), 72.0)

    def test_cap_exposure_steps(self) -> None:
        clock = mechanism12_simulation_clock()
        self.assertEqual(clock.cap_duration_steps(30), 30)
        self.assertEqual(clock.cap_duration_steps(120), 120)
        self.assertEqual(clock.cap_duration_steps(300), 300)
        for exposure_s in CAP_EXPOSURE_SECONDS:
            self.assertEqual(clock.cap_duration_steps(exposure_s), exposure_s)

    def test_g1_dwell_minute_template(self) -> None:
        dt_h = read_template_time_step_hours(M11_TEMPLATE)
        hours = template_abm_value_to_optimizer_hours(
            "normoxic_CC/phase_dwell/G1",
            494.0,
            time_step_h=dt_h,
        )
        self.assertAlmostEqual(hours, 8.233333, places=3)

    def test_validate_control_template(self) -> None:
        clock = mechanism11_simulation_clock()
        report = validate_simulation_clock(M11_TEMPLATE, (0, 24, 48, 72), clock)
        self.assertEqual(report.warnings, ())
        self.assertAlmostEqual(read_template_simulation_hours(M11_TEMPLATE), 72.0)

    def test_validate_m12_template(self) -> None:
        clock = mechanism12_simulation_clock()
        report = validate_simulation_clock(M12_TEMPLATE, (0, 24, 48, 72), clock)
        self.assertEqual(report.warnings, ())
        self.assertAlmostEqual(read_template_simulation_hours(M12_TEMPLATE), 72.0)

    def test_hours_to_steps_dt_one_legacy(self) -> None:
        self.assertEqual(hours_to_steps(8.0, 1.0), 8)
        self.assertEqual(seconds_to_steps(30, seconds_to_time_step_h(1.0)), 30)


if __name__ == "__main__":
    unittest.main()
