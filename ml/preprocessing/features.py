"""Vectorized validation for training rows against the live feature schema."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nids_engine.features import (
    BINARY_FEATURE_NAMES,
    FEATURE_NAMES,
    INTEGER_FEATURE_NAMES,
    PROTOCOL_FEATURE_NAMES,
)


class FeatureDataError(ValueError):
    """Raised when a training matrix violates the inference feature schema."""


def validate_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return ordered float-valued features after strict range and type checks."""

    if tuple(frame.columns) != FEATURE_NAMES:
        raise FeatureDataError("feature columns must exactly match schema 1.0 order")
    numeric = frame.apply(pd.to_numeric, errors="coerce").astype("float64")
    values = numeric.to_numpy(copy=False)
    if not np.isfinite(values).all():
        raise FeatureDataError("feature matrix contains missing, non-numeric, or non-finite values")
    if (values < 0).any():
        raise FeatureDataError("feature matrix contains negative values")

    columns = {name: numeric[name].to_numpy(copy=False) for name in FEATURE_NAMES}
    for name in INTEGER_FEATURE_NAMES:
        if not np.equal(columns[name], np.floor(columns[name])).all():
            raise FeatureDataError(f"{name} must contain integer-valued measurements")
    for name in ("endpoint_a_port", "endpoint_b_port"):
        if (columns[name] > 65535).any():
            raise FeatureDataError(f"{name} contains a value outside the valid port range")
    for name in BINARY_FEATURE_NAMES:
        if not np.isin(columns[name], (0.0, 1.0)).all():
            raise FeatureDataError(f"{name} must contain only 0 or 1")
    protocol_values = np.column_stack([columns[name] for name in PROTOCOL_FEATURE_NAMES])
    if not np.equal(protocol_values.sum(axis=1), 1.0).all():
        raise FeatureDataError("exactly one protocol feature must be set for every row")
    if not np.array_equal(columns["total_packets"], columns["forward_packets"] + columns["reverse_packets"]):
        raise FeatureDataError("total_packets must equal the directional packet counts")
    if not np.array_equal(columns["total_bytes"], columns["forward_bytes"] + columns["reverse_bytes"]):
        raise FeatureDataError("total_bytes must equal the directional byte counts")
    if (columns["total_packets"] < 1).any():
        raise FeatureDataError("each flow must contain at least one packet")
    if (columns["min_packet_size"] > columns["max_packet_size"]).any():
        raise FeatureDataError("min_packet_size cannot exceed max_packet_size")
    for direction in ("forward", "reverse"):
        minimum = columns[f"{direction}_packet_size_min"]
        maximum = columns[f"{direction}_packet_size_max"]
        packets = columns[f"{direction}_packets"]
        missing = columns[f"{direction}_packet_size_missing"]
        if (minimum > maximum).any():
            raise FeatureDataError(f"{direction} packet-size minimum cannot exceed maximum")
        if not np.array_equal(missing, (packets == 0).astype("float64")):
            raise FeatureDataError(f"{direction} packet-size missing flag must match its packet count")
        if ((missing == 1) & ((minimum != 0) | (maximum != 0))).any():
            raise FeatureDataError(f"missing {direction} packet sizes must be encoded as zero")
    for endpoint in ("endpoint_a", "endpoint_b"):
        missing = columns[f"{endpoint}_port_missing"]
        port = columns[f"{endpoint}_port"]
        if ((missing == 1) & (port != 0)).any():
            raise FeatureDataError(f"missing {endpoint} ports must be encoded as zero")

    duration = columns["flow_duration_seconds"]
    packets_per_second = np.divide(
        columns["total_packets"], duration, out=np.zeros_like(duration), where=duration > 0
    )
    bytes_per_second = np.divide(columns["total_bytes"], duration, out=np.zeros_like(duration), where=duration > 0)
    average_packet_size = columns["total_bytes"] / columns["total_packets"]
    for name, actual, expected in (
        ("packets_per_second", columns["packets_per_second"], packets_per_second),
        ("bytes_per_second", columns["bytes_per_second"], bytes_per_second),
        ("average_packet_size", columns["average_packet_size"], average_packet_size),
    ):
        if not np.allclose(actual, expected, rtol=1e-9, atol=1e-9):
            raise FeatureDataError(f"{name} is inconsistent with its source counters")
    return numeric
