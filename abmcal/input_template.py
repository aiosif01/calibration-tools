from __future__ import annotations

from pathlib import Path
from typing import Mapping, Any
import csv


def render_template(
    template_path: str | Path,
    output_path: str | Path,
    *,
    placeholder_values: Mapping[str, Any] | None = None,
    parameter_overrides: Mapping[str, Any] | None = None,
) -> None:
    """
    Render an ABM4bio input CSV.

    Supports both styles:
    1) Placeholder replacement, e.g. __parameter_1__.
    2) Row override by ABM4bio parameter_name.
    """
    template_path = Path(template_path)
    output_path = Path(output_path)
    text = template_path.read_text()

    if placeholder_values:
        for key, value in placeholder_values.items():
            token = key if str(key).startswith("__") else f"__{key}__"
            text = text.replace(token, _format_value(value))

    if parameter_overrides:
        lines = text.splitlines()
        rendered_lines = []
        applied_keys: set[str] = set()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("###"):
                rendered_lines.append(_sanitize_comment_line(line))
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[0] in parameter_overrides:
                parts[2] = _format_value(parameter_overrides[parts[0]])
                applied_keys.add(parts[0])
                rendered_lines.append(",".join(parts))
            else:
                rendered_lines.append(line)
        for key, value in parameter_overrides.items():
            if key in applied_keys:
                continue
            rendered_lines.append(f"{key},{_csv_type_name(value)},{_format_value(value)}")
        text = "\n".join(rendered_lines) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text)


def _sanitize_comment_line(line: str) -> str:
    """ABM4bio CSV rows must have exactly 3 columns; commas in ### headers break parsing."""
    stripped = line.strip()
    if stripped.startswith("###") and stripped.endswith(",###,###"):
        prefix = "### "
        suffix = ",###,###"
        body = stripped[len("###") : -len(suffix)].strip()
        body = body.replace(",", " ")
        return f"{prefix}{body}{suffix}"
    return line


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def _csv_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"
