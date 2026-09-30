"""Envelope v1 serialization and validation shared by producers and consumers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import math
import os
import re
import time
from typing import Any


_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"[0-7][0-9A-HJKMNP-TV-Z]{25}\Z")


@dataclass(frozen=True)
class Envelope:
    schema_version: int
    tenant_id: str
    robot_id: str
    stream: str
    boot_id: str
    seq: int
    seq_origin: str
    source_ts_ns: int
    bridge_rx_ts_ns: int
    message_id: str
    payload: dict[str, Any]


def new_boot_id() -> str:
    """Generate a ULID once when the sequence-owning process starts."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(_ULID_ALPHABET[(value >> shift) & 31] for shift in range(125, -1, -5))


def _identity(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or ":" in value:
        raise ValueError(f"{name} must be a non-empty string without ':'")
    return value


def make_message_id(
    tenant_id: str, robot_id: str, stream: str, boot_id: str, seq: int
) -> str:
    """Build the stable deduplication ID for one boot and stream sequence."""
    _identity(tenant_id, "tenant_id")
    _identity(robot_id, "robot_id")
    _identity(stream, "stream")
    if not isinstance(boot_id, str) or _ULID_RE.fullmatch(boot_id) is None:
        raise ValueError("boot_id must be a 26-character Crockford base32 ULID")
    if type(seq) is not int or seq < 0:
        raise ValueError("seq must be a non-negative integer")
    return f"{tenant_id}:{robot_id}:{stream}:{boot_id}:{seq}"


def kafka_key(tenant_id: str, robot_id: str) -> str:
    """Keep all streams and boots of a robot on the same Kafka key."""
    return f"{_identity(tenant_id, 'tenant_id')}:{_identity(robot_id, 'robot_id')}"


def _validate_json_value(value: Any) -> None:
    if value is None or isinstance(value, (str, bool)) or type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("payload must not contain NaN or Infinity")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("payload object keys must be strings")
            _validate_json_value(item)
        return
    raise ValueError("payload must contain only JSON-compatible values")


def validate(envelope: Envelope) -> None:
    """Reject malformed identity, timestamps, IDs and non-JSON payloads."""
    if not isinstance(envelope, Envelope):
        raise TypeError("expected Envelope")
    if type(envelope.schema_version) is not int or envelope.schema_version != 1:
        raise ValueError("schema_version must be 1")
    expected_id = make_message_id(
        envelope.tenant_id,
        envelope.robot_id,
        envelope.stream,
        envelope.boot_id,
        envelope.seq,
    )
    if envelope.seq_origin not in ("bridge", "source"):
        raise ValueError("seq_origin must be 'bridge' or 'source'")
    for name in ("source_ts_ns", "bridge_rx_ts_ns"):
        value = getattr(envelope, name)
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if envelope.message_id != expected_id:
        raise ValueError("message_id does not match envelope identity and seq")
    if not isinstance(envelope.payload, dict):
        raise ValueError("payload must be a JSON object")
    _validate_json_value(envelope.payload)


def to_json(envelope: Envelope) -> str:
    validate(envelope)
    return json.dumps(asdict(envelope), allow_nan=False, separators=(",", ":"))


def _reject_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {token}")


def from_json(raw: str | bytes) -> Envelope:
    data = json.loads(raw, parse_constant=_reject_nonfinite)
    if not isinstance(data, dict):
        raise ValueError("envelope JSON must be an object")
    expected = {field.name for field in fields(Envelope)}
    missing = expected - data.keys()
    extra = data.keys() - expected
    if missing or extra:
        raise ValueError(f"invalid envelope fields; missing={sorted(missing)}, extra={sorted(extra)}")
    envelope = Envelope(**data)
    validate(envelope)
    return envelope
