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

RAW_RECEIPT_PAYLOAD_1 = """{"payload":{"job_uuid":"01584e70-3242-40b6-be69-65bca9d423c2","miner_hotkey":"5GBm3LTJpUGrkX9FXTS65Fx3Cqpz9zThgPx6gPuNdhdjjLm3","validator_hotkey":"5HpWwsSCHhmFuBtQPskPbjM4As3oXHH8Mgh9NGbyyiuHPABx","time_started":"2024-07-02T18:31:41.259730Z","time_took_us":30000000,"score_str":"0.1234","executor_class":"spin_up-4min.gpu-24gb"},"validator_signature":"0x5cd3a2a17d1bd844b1654aca30db1e9b76f4312c5b6d937c446696a2ac2ef848de1b306cf655b402a8a41dc8f79c0880066b63f380251ab5d49ef6c11ad08888","miner_signature":"0xf231018a49d6c95ba1fdd2a41df56564627bddbad65e0722cb3bf17fee99d634d0aa7c0f35ed2ebb2f8ff981b285222cecc80c215d9e0887ced0c52ce32dfd86"}"""
RAW_RECEIPT_PAYLOAD_2 = """{"payload":{"job_uuid":"d10f1c3e-f90f-4fda-bf1b-38bb6d633fc3","miner_hotkey":"5GBm3LTJpUGrkX9FXTS65Fx3Cqpz9zThgPx6gPuNdhdjjLm3","validator_hotkey":"5HpWwsSCHhmFuBtQPskPbjM4As3oXHH8Mgh9NGbyyiuHPABx","time_started":"2024-07-02T18:32:34.172187Z","time_took_us":30000000,"score_str":"0.1234","executor_class":"spin_up-4min.gpu-24gb"},"validator_signature":"0xb0ab8d589348661ea3f0f990e3bcecf73bdd0e7d57589f8c21f74af8ffcb22024f41754b15ce97161353996b960d84c8a56785d383381a552263f473a861938d","miner_signature":"0xe049797f3120e781793e93aea5874887ff81c2f4a4fb3280f2fb28ba5f501f0dc29a8c6785fc89ca79bf901846f1fccf5b951a26ddd6ab710a2e4fd0f0ea6f8c"}"""

MINER_HOTKEY = "5GBm3LTJpUGrkX9FXTS65Fx3Cqpz9zThgPx6gPuNdhdjjLm3"
PAYLOAD_2_MINER_SIGNATURE = "0xe049797f3120e781793e93aea5874887ff81c2f4a4fb3280f2fb28ba5f501f0dc29a8c6785fc89ca79bf901846f1fccf5b951a26ddd6ab710a2e4fd0f0ea6f8c"
PAYLOAD_2_VALIDATOR_SIGNATURE = "0xb0ab8d589348661ea3f0f990e3bcecf73bdd0e7d57589f8c21f74af8ffcb22024f41754b15ce97161353996b960d84c8a56785d383381a552263f473a861938d"


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
            "executor_class",
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
                payload.get("executor_class", ""),
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
                    hotkey=MINER_HOTKEY,
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
        assert instance.executor_class == receipt_payload["payload"]["executor_class"]


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
        MINER_HOTKEY,
        MINER_HOTKEY[:-4] + "AAAA",
    )
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [RAW_RECEIPT_PAYLOAD_1, invalid_receipt_payload])

    # only the valid receipt should be stored
    assert JobReceipt.objects.all().count() == 1
    assert str(JobReceipt.objects.get().job_uuid) == json.loads(RAW_RECEIPT_PAYLOAD_1)["payload"]["job_uuid"]


@pytest.mark.django_db(transaction=True)
def test__fetch_receipts__invalid_miner_signature_skipped(monkeypatch, mocked_responses):
    invalid_char = "0" if PAYLOAD_2_MINER_SIGNATURE[-1] != "0" else "1"
    invalid_receipt_payload = RAW_RECEIPT_PAYLOAD_2.replace(
        PAYLOAD_2_MINER_SIGNATURE,
        PAYLOAD_2_MINER_SIGNATURE[:-1] + invalid_char,
    )
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [RAW_RECEIPT_PAYLOAD_1, invalid_receipt_payload])

    # only the valid receipt should be stored
    assert JobReceipt.objects.all().count() == 1
    assert str(JobReceipt.objects.get().job_uuid) == json.loads(RAW_RECEIPT_PAYLOAD_1)["payload"]["job_uuid"]


@pytest.mark.django_db(transaction=True)
def test__fetch_receipts__invalid_validator_signature_skipped(monkeypatch, mocked_responses):
    invalid_char = "0" if PAYLOAD_2_VALIDATOR_SIGNATURE[-1] != "0" else "1"
    invalid_receipt_payload = RAW_RECEIPT_PAYLOAD_2.replace(
        PAYLOAD_2_VALIDATOR_SIGNATURE,
        PAYLOAD_2_VALIDATOR_SIGNATURE[:-1] + invalid_char,
    )
    fetch_receipts_test_helper(monkeypatch, mocked_responses, [RAW_RECEIPT_PAYLOAD_1, invalid_receipt_payload])

    # only the valid receipt should be stored
    assert JobReceipt.objects.all().count() == 1
    assert str(JobReceipt.objects.get().job_uuid) == json.loads(RAW_RECEIPT_PAYLOAD_1)["payload"]["job_uuid"]
