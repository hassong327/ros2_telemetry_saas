import json
import math

import pytest

from telemetry_schema import (
    Envelope,
    from_json,
    kafka_key,
    make_message_id,
    new_boot_id,
    to_json,
    validate,
)


def example_envelope(**overrides):
    data = {
        "schema_version": 1,
        "tenant_id": "demo-factory",
        "robot_id": "robot_001",
        "stream": "imu",
        "boot_id": new_boot_id(),
        "seq": 12,
        "seq_origin": "bridge",
        "source_ts_ns": 1_790_000_000_000_000_000,
        "bridge_rx_ts_ns": 1_790_000_000_000_200_000,
        "payload": {"ax": 0.01, "nested": [True, {"az": 9.81}]},
    }
    data.update(overrides)
    data.setdefault(
        "message_id",
        make_message_id(
            data["tenant_id"], data["robot_id"], data["stream"], data["boot_id"], data["seq"]
        ),
    )
    return Envelope(**data)


def test_ulid_and_message_id_include_boot_identity():
    first_boot = new_boot_id()
    second_boot = new_boot_id()
    assert len(first_boot) == 26
    assert len(second_boot) == 26
    assert first_boot != second_boot
    first = make_message_id("tenant", "robot", "imu", first_boot, 0)
    second = make_message_id("tenant", "robot", "imu", second_boot, 0)
    assert first == f"tenant:robot:imu:{first_boot}:0"
    assert first != second
    assert kafka_key("tenant", "robot") == "tenant:robot"


def test_json_round_trip_preserves_envelope():
    envelope = example_envelope()
    encoded = to_json(envelope)
    assert from_json(encoded) == envelope
    assert json.loads(encoded)["seq_origin"] == "bridge"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_rejects_nonfinite_payload_values(value):
    with pytest.raises(ValueError, match="NaN or Infinity"):
        validate(example_envelope(payload={"samples": [value]}))
    raw = to_json(example_envelope())
    with pytest.raises(ValueError, match="non-finite"):
        from_json(raw.replace("0.01", str(value).replace("inf", "Infinity").replace("nan", "NaN")))


def test_rejects_missing_required_field():
    data = json.loads(to_json(example_envelope()))
    del data["boot_id"]
    with pytest.raises(ValueError, match="missing=.*boot_id"):
        from_json(json.dumps(data))


def test_rejects_invalid_boot_id_and_mismatched_message_id():
    with pytest.raises(ValueError, match="ULID"):
        validate(example_envelope(boot_id="not-a-ulid", message_id="invalid"))
    with pytest.raises(ValueError, match="message_id"):
        validate(example_envelope(message_id="other"))


def test_rejects_invalid_types_and_seq_origin():
    with pytest.raises(ValueError, match="seq"):
        validate(example_envelope(seq=True, message_id="invalid"))
    with pytest.raises(ValueError, match="seq_origin"):
        validate(example_envelope(seq_origin="publisher"))
