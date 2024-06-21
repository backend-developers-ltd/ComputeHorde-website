import datetime
import json
import time

import bittensor
import pytest
from rest_framework.test import APIClient

from project.stats_collector.models import ValidatorSystemEvent


@pytest.fixture
def api_client():
    return APIClient()


def signature_headers(keypair: bittensor.Keypair, timestamp=None):
    signing_timestamp = timestamp or int(time.time())
    signature = keypair.sign(
        json.dumps(
            {
                "signing_timestamp": signing_timestamp,
                "validator_ss58_address": keypair.ss58_address,
            },
            sort_keys=True,
        )
    )
    return {
        "Validator-Signing-Timestamp": str(signing_timestamp),
        "Validator-Signature": signature,
    }


DATA = [
    {
        "type": "WEIGHT_SETTING_FAIL",
        "subtype": "GENERIC",
        "timestamp": str(datetime.datetime(2024, 1, 1)),
        "data": {},
    },
    {
        "type": "WEIGHT_SETTING_SUCCESS",
        "subtype": "SUCCESS",
        "timestamp": str(datetime.datetime(2024, 1, 1, 12)),
        "data": {"try_number": 100},
    },
]


@pytest.mark.django_db(transaction=True)
def test_old_signature(api_client, validator, keypair):
    response = api_client.post(
        f"/stats_collector/v0/validator/{keypair.ss58_address}/system_events",
        data={"data": DATA},
        headers=signature_headers(keypair, int(time.time() - 100)),
    )
    assert response.status_code == 401
    assert response.content == b'{"detail":"Signature too old"}'


@pytest.mark.django_db(transaction=True)
def test_wrong_signature(api_client, validator, keypair, other_keypair):
    response = api_client.post(
        f"/stats_collector/v0/validator/{keypair.ss58_address}/system_events",
        data={"data": DATA},
        headers=signature_headers(other_keypair),
    )
    assert response.status_code == 401
    assert response.content == b'{"detail":"Signature invalid"}'


@pytest.mark.django_db(transaction=True)
def test_missing_validator(api_client, validator, keypair):
    validator.delete()
    response = api_client.post(
        f"/stats_collector/v0/validator/{keypair.ss58_address}/system_events",
        data={"data": DATA},
        headers=signature_headers(keypair),
    )
    assert response.status_code == 401
    assert response.content == b'{"detail":"Validator unknown"}'


@pytest.mark.django_db(transaction=True)
def test_inactive_validator(api_client, validator, keypair):
    validator.is_active = False
    validator.save()
    response = api_client.post(
        f"/stats_collector/v0/validator/{keypair.ss58_address}/system_events",
        data={"data": DATA},
        headers=signature_headers(keypair),
    )
    assert response.status_code == 401
    assert response.content == b'{"detail":"Validator inactive"}'


@pytest.mark.django_db(transaction=True)
def test_ok(api_client, validator, keypair):
    response = api_client.post(
        f"/stats_collector/v0/validator/{keypair.ss58_address}/system_events",
        data=DATA,
        headers=signature_headers(keypair),
    )
    assert response.status_code == 201
    assert [
        {
            "validator": e.validator,
            "type": e.type,
            "subtype": e.subtype,
            "timestamp": e.timestamp,
            "data": e.data,
        }
        for e in ValidatorSystemEvent.objects.order_by("timestamp").all()
    ] == [
        {
            "data": {},
            "subtype": "GENERIC",
            "timestamp": datetime.datetime(2024, 1, 1, 0, 0, tzinfo=datetime.UTC),
            "type": "WEIGHT_SETTING_FAIL",
            "validator": validator,
        },
        {
            "data": {"try_number": 100},
            "subtype": "SUCCESS",
            "timestamp": datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC),
            "type": "WEIGHT_SETTING_SUCCESS",
            "validator": validator,
        },
    ]
