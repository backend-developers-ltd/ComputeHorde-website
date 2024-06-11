import csv
import io
import json
from datetime import datetime
from typing import NamedTuple

import pytest
from asgiref.sync import sync_to_async
from constance import config

from ..models import Channel, JobReceipt, Validator
from ..tasks import fetch_receipts, sync_metagraph

RAW_RECEIPT_PAYLOAD_1 = """{"miner_signature": "0xf840fe3fd112351b4a41dc8519b7f0c493af16e67bb98a8168654d8687b3ae6683bf6e8f36a96ecd70fa207ce332ba0c62e06e66f3d51ea01999e4252db0dd82", "payload": {"job_uuid": "0cce29bb-ea05-4c5e-a274-f185ccb117bc", "miner_hotkey": "5CPhGRp4cdEG4KSui7VQixHhvN5eBUSnMYeUF5thdxm4sKtz", "score_str": "1.661293", "time_started": "2024-05-18T16:00:11.796484+00:00", "time_took_us": 15241820, "validator_hotkey": "5Ctd7bcs7Fgsh5KzZuJZ72fMBvPp5Xwxj4RqWZ1m3UTM7oor"}, "validator_signature": "0x829817f57d46bd700c7fb979f97aa5f97378ef25c51c617704ed831a4386710b56a19dc3ed869d23e0e25da8636d92d68e1ef04efc55679e5914df984f5f3e8d"}"""
RAW_RECEIPT_PAYLOAD_2 = """{"miner_signature": "0x1ec4f532d5b0f5494c5dfa5f84db7fe661202291367ffd798e20815700cd5a4146cb3dab713dead03b41f0085146b97d18df53ef22bb8fe49af84f79c296c68a", "payload": {"job_uuid": "0e93c887-879f-4332-a807-a42f42dfd73d", "miner_hotkey": "5CPhGRp4cdEG4KSui7VQixHhvN5eBUSnMYeUF5thdxm4sKtz", "score_str": "1.692837", "time_started": "2024-05-18T00:00:12.922840+00:00", "time_took_us": 27644673, "validator_hotkey": "5Ctd7bcs7Fgsh5KzZuJZ72fMBvPp5Xwxj4RqWZ1m3UTM7oor"}, "validator_signature": "0xe6717cbf7b5c30a4e9fc4b307be08f8624490ca1e693eb594adc4d60936aad3e690fa8ddd3e8edf7d4e81994487b996ec287cc9dddf4df7f3b634033c0bf658c"}"""


class MockedAxonInfo(NamedTuple):
    is_serving: bool
    ip: str = ""
    port: int = 0


class MockedNeuron(NamedTuple):
    hotkey: str
    axon_info: MockedAxonInfo
    stake: float


validator_params = dict(
    axon_info=MockedAxonInfo(is_serving=False),
    stake=1.0,
)

miner_params = dict(
    axon_info=MockedAxonInfo(is_serving=True),
    stake=0.0,
)


@pytest.mark.django_db(transaction=True)
def test__sync_metagraph__activation(monkeypatch):
    import bittensor

    validators = Validator.objects.bulk_create(
        [
            Validator(ss58_address="remains_active", is_active=True),
            Validator(ss58_address="is_deactivated", is_active=True),
            Validator(ss58_address="remains_inactive", is_active=False),
            Validator(ss58_address="is_activated", is_active=False),
        ]
    )

    class MockedMetagraph:
        def __init__(self, *args, **kwargs):
            self.neurons = [
                MockedNeuron(hotkey="remains_active", **validator_params),
                MockedNeuron(hotkey="is_deactivated", **miner_params),
                MockedNeuron(hotkey="remains_inactive", **miner_params),
                MockedNeuron(hotkey="is_activated", **validator_params),
                MockedNeuron(hotkey="new_validator", **validator_params),
                MockedNeuron(hotkey="new_miner", **miner_params),
            ]

    with monkeypatch.context() as mp:
        mp.setattr(bittensor, "metagraph", MockedMetagraph)
        sync_metagraph()

    validators = Validator.objects.order_by("id").values_list("ss58_address", "is_active")
    assert list(validators) == [
        tuple(d.values())
        for d in [
            dict(ss58_address="remains_active", is_active=True),
            dict(ss58_address="is_deactivated", is_active=False),
            dict(ss58_address="remains_inactive", is_active=False),
            dict(ss58_address="is_activated", is_active=True),
            dict(ss58_address="new_validator", is_active=True),
        ]
    ]


@pytest.mark.django_db(transaction=True)
def test__sync_metagraph__limit__no_our_validator(monkeypatch):
    """When there is validator limit"""

    import bittensor

    class MockedMetagraph:
        def __init__(self, *args, **kwargs):
            self.neurons = [MockedNeuron(hotkey=str(i), **(validator_params | {"stake": 10 * i})) for i in range(1, 33)]

    config.VALIDATORS_LIMIT = 4

    with monkeypatch.context() as mp:
        mp.setattr(bittensor, "metagraph", MockedMetagraph)
        sync_metagraph()

    validators = Validator.objects.order_by("ss58_address").values_list("ss58_address")
    assert list(validators) == [
        tuple(d.values())
        for d in [
            dict(ss58_address="29"),
            dict(ss58_address="30"),
            dict(ss58_address="31"),
            dict(ss58_address="32"),
        ]
    ]


@pytest.mark.django_db(transaction=True)
def test__sync_metagraph__limit_and_our_validator__wrong(monkeypatch):
    """When there is validator limit and ours is not in validators list"""

    import bittensor

    class MockedMetagraph:
        def __init__(self, *args, **kwargs):
            self.neurons = [MockedNeuron(hotkey=str(i), **(validator_params | {"stake": 10 * i})) for i in range(1, 33)]

    config.VALIDATORS_LIMIT = 4
    config.OUR_VALIDATOR_SS58_ADDRESS = "99"

    with monkeypatch.context() as mp:
        mp.setattr(bittensor, "metagraph", MockedMetagraph)
        sync_metagraph()

    validators = Validator.objects.order_by("ss58_address").values_list("ss58_address")
    assert list(validators) == [
        tuple(d.values())
        for d in [
            dict(ss58_address="29"),
            dict(ss58_address="30"),
            dict(ss58_address="31"),
            dict(ss58_address="32"),
        ]
    ]


@pytest.mark.django_db(transaction=True)
def test__sync_metagraph__limit_and_our_validator__inside_limit(monkeypatch):
    """When there is validator limit and ours is one of best validators"""

    import bittensor

    class MockedMetagraph:
        def __init__(self, *args, **kwargs):
            self.neurons = [MockedNeuron(hotkey=str(i), **(validator_params | {"stake": 10 * i})) for i in range(1, 33)]

    config.VALIDATORS_LIMIT = 4
    config.OUR_VALIDATOR_SS58_ADDRESS = "30"

    with monkeypatch.context() as mp:
        mp.setattr(bittensor, "metagraph", MockedMetagraph)
        sync_metagraph()

    validators = Validator.objects.order_by("ss58_address").values_list("ss58_address")
    assert list(validators) == [
        tuple(d.values())
        for d in [
            dict(ss58_address="29"),
            dict(ss58_address="30"),
            dict(ss58_address="31"),
            dict(ss58_address="32"),
        ]
    ]


@pytest.mark.django_db(transaction=True)
def test__sync_metagraph__limit_and_our_validator__outside_limit(monkeypatch):
    """When there is validator limit and ours is not one of best validators"""

    import bittensor

    class MockedMetagraph:
        def __init__(self, *args, **kwargs):
            self.neurons = [MockedNeuron(hotkey=str(i), **(validator_params | {"stake": 10 * i})) for i in range(1, 33)]

    config.VALIDATORS_LIMIT = 4
    config.OUR_VALIDATOR_SS58_ADDRESS = "25"

    with monkeypatch.context() as mp:
        mp.setattr(bittensor, "metagraph", MockedMetagraph)
        sync_metagraph()

    validators = Validator.objects.order_by("ss58_address").values_list("ss58_address")
    assert list(validators) == [
        tuple(d.values())
        for d in [
            dict(ss58_address="25"),
            dict(ss58_address="30"),
            dict(ss58_address="31"),
            dict(ss58_address="32"),
        ]
    ]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test__websocket__disconnect_validator_if_become_inactive(
    monkeypatch,
    communicator,
    authenticated,
    validator,
    job,
    dummy_job_params,
):
    """Check that validator is disconnected if it becomes inactive"""
    import bittensor

    await communicator.receive_json_from()
    assert await Channel.objects.filter(validator=validator).aexists()

    class MockedMetagraph:
        def __init__(self, *args, **kwargs):
            self.neurons = [
                MockedNeuron(hotkey=validator.ss58_address, **miner_params),
            ]

    with monkeypatch.context() as mp:
        mp.setattr(bittensor, "metagraph", MockedMetagraph)
        await sync_to_async(sync_metagraph)()

    assert not await Channel.objects.filter(validator=validator).aexists()
    with pytest.raises(TimeoutError):
        await communicator.receive_json_from()


def fetch_receipts_test_helper(monkeypatch, mocked_responses, raw_receipt_payloads):
    buf = io.StringIO()
    csv_writer = csv.writer(buf)
    csv_writer.writerow(
        [
            "job_uuid",
            "miner_hotkey",
            "validator_hotkey",
            "time_started",
            "time_took_us",
            "score_str",
            "validator_signature",
            "miner_signature",
        ]
    )
    for raw_receipt_payload in raw_receipt_payloads:
        receipt = json.loads(raw_receipt_payload)
        payload = receipt.get("payload", {})
        csv_writer.writerow(
            [
                payload.get("job_uuid", ""),
                payload.get("miner_hotkey", ""),
                payload.get("validator_hotkey", ""),
                payload.get("time_started", ""),
                payload.get("time_took_us", ""),
                payload.get("score_str", ""),
                receipt.get("validator_signature", ""),
                receipt.get("miner_signature", ""),
            ]
        )

    buf.seek(0)

    mocked_responses.get(
        "http://127.0.0.1:8000/receipts/receipts.csv", status=404
    )  # this one should be gracefully ignored
    mocked_responses.get("http://127.0.0.2:8000/receipts/receipts.csv", body=buf.read())

    class MockedMetagraph:
        def __init__(self, *args, **kwargs):
            self.neurons = [
                MockedNeuron(
                    hotkey="non-serving",
                    axon_info=MockedAxonInfo(is_serving=True, ip="127.0.0.1", port=8000),
                    stake=0.0,
                ),
                MockedNeuron(
                    hotkey="5CPhGRp4cdEG4KSui7VQixHhvN5eBUSnMYeUF5thdxm4sKtz",
                    axon_info=MockedAxonInfo(is_serving=True, ip="127.0.0.2", port=8000),
                    stake=0.0,
                ),
            ]

    with monkeypatch.context() as mp:
        import bittensor

        mp.setattr(bittensor, "metagraph", MockedMetagraph)
        fetch_receipts()


@pytest.mark.django_db(transaction=True)
def test__fetch_receipts__happy_path(monkeypatch, mocked_responses):
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [RAW_RECEIPT_PAYLOAD_1, RAW_RECEIPT_PAYLOAD_2])

    assert JobReceipt.objects.all().count() == 2

    for raw_receipt_payload in [RAW_RECEIPT_PAYLOAD_1, RAW_RECEIPT_PAYLOAD_2]:
        receipt_payload = json.loads(raw_receipt_payload)
        instance = JobReceipt.objects.get(job_uuid=receipt_payload["payload"]["job_uuid"])
        assert instance.miner_hotkey == receipt_payload["payload"]["miner_hotkey"]
        assert instance.validator_hotkey == receipt_payload["payload"]["validator_hotkey"]
        assert instance.time_started == datetime.fromisoformat(receipt_payload["payload"]["time_started"])
        assert instance.time_took_us == receipt_payload["payload"]["time_took_us"]
        assert instance.score_str == receipt_payload["payload"]["score_str"]


@pytest.mark.django_db(transaction=True)
def test__fetch_receipts__invalid_receipt_skipped(monkeypatch, mocked_responses):
    invalid_receipt_payload = json.dumps({"payload": {"job_uuid": "invalid"}})
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [invalid_receipt_payload, RAW_RECEIPT_PAYLOAD_1])

    # only the valid receipt should be stored
    assert JobReceipt.objects.all().count() == 1
    assert str(JobReceipt.objects.get().job_uuid) == json.loads(RAW_RECEIPT_PAYLOAD_1)["payload"]["job_uuid"]


@pytest.mark.django_db(transaction=True)
def test__fetch_receipts__miner_hotkey_mismatch_skipped(monkeypatch, mocked_responses):
    invalid_receipt_payload = RAW_RECEIPT_PAYLOAD_2.replace(
        "5CPhGRp4cdEG4KSui7VQixHhvN5eBUSnMYeUF5thdxm4sKtz",
        "different-miner",
    )
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [RAW_RECEIPT_PAYLOAD_1, invalid_receipt_payload])

    # only the valid receipt should be stored
    assert JobReceipt.objects.all().count() == 1
    assert str(JobReceipt.objects.get().job_uuid) == json.loads(RAW_RECEIPT_PAYLOAD_1)["payload"]["job_uuid"]


@pytest.mark.django_db(transaction=True)
def test__fetch_receipts__invalid_miner_signature_skipped(monkeypatch, mocked_responses):
    invalid_receipt_payload = RAW_RECEIPT_PAYLOAD_2.replace(
        "0x1ec4f532d5b0f5494c5dfa5f84db7fe661202291367ffd798e20815700cd5a4146cb3dab713dead03b41f0085146b97d18df53ef22bb8fe49af84f79c296c68a",
        "0x1ec4f532d5b0f5494c5dfa5f84db7fe661202291367ffd798e20815700cd5a4146cb3dab713dead03b41f0085146b97d18df53ef22bb8fe49af84f79c296c68b",
    )
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [RAW_RECEIPT_PAYLOAD_1, invalid_receipt_payload])

    # only the valid receipt should be stored
    assert JobReceipt.objects.all().count() == 1
    assert str(JobReceipt.objects.get().job_uuid) == json.loads(RAW_RECEIPT_PAYLOAD_1)["payload"]["job_uuid"]


@pytest.mark.django_db(transaction=True)
def test__fetch_receipts__invalid_validator_signature_skipped(monkeypatch, mocked_responses):
    invalid_receipt_payload = RAW_RECEIPT_PAYLOAD_2.replace(
        "0xe6717cbf7b5c30a4e9fc4b307be08f8624490ca1e693eb594adc4d60936aad3e690fa8ddd3e8edf7d4e81994487b996ec287cc9dddf4df7f3b634033c0bf658c",
        "0xe6717cbf7b5c30a4e9fc4b307be08f8624490ca1e693eb594adc4d60936aad3e690fa8ddd3e8edf7d4e81994487b996ec287cc9dddf4df7f3b634033c0bf658d",
    )
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [RAW_RECEIPT_PAYLOAD_1, invalid_receipt_payload])

    # only the valid receipt should be stored
    assert JobReceipt.objects.all().count() == 1
    assert str(JobReceipt.objects.get().job_uuid) == json.loads(RAW_RECEIPT_PAYLOAD_1)["payload"]["job_uuid"]
