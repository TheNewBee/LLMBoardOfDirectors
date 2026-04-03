from __future__ import annotations


def parse_key_value_strings(items: list[str], *, name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"{name}: expected KEY=value, got {raw!r}")
        key, value = raw.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not value:
            raise ValueError(f"{name}: empty key or value in {raw!r}")
        out[key] = value
    return out


def parse_key_value_floats(
    items: list[str],
    *,
    name: str,
    low: float = 0.0,
    high: float = 1.0,
) -> dict[str, float]:
    raw = parse_key_value_strings(items, name=name)
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            parsed = float(value)
        except ValueError as exc:
            raise ValueError(f"{name}: {key}={value!r} is not a number") from exc
        if parsed < low or parsed > high:
            raise ValueError(f"{name}: {key} must be in [{low}, {high}], got {parsed}")
        out[key] = parsed
    return out
