import datetime
import json
import time

import bittensor
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..core.models import Validator
from .models import ValidatorSystemEvent

MAX_SIGNATURE_AGE = 60


class ValidatorSystemEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidatorSystemEvent
        fields = ["type", "subtype", "timestamp", "data", "validator"]


def get_validator_id(request, validator_ss58_address) -> int:
    signing_timestamp = request.headers.get("Validator-Signing-Timestamp")

    try:
        signing_timestamp = int(signing_timestamp)
    except ValueError:
        raise NotAuthenticated("Invalid Signing Timestamp")

    if int(time.time()) - signing_timestamp > MAX_SIGNATURE_AGE:
        raise NotAuthenticated("Signature too old")

    signature = request.headers.get("Validator-Signature")
    if not signature:
        raise NotAuthenticated("No signature")

    signed_data = json.dumps(
        {"signing_timestamp": signing_timestamp, "validator_ss58_address": validator_ss58_address},
        sort_keys=True,
    )

    try:
        keypair = bittensor.Keypair(ss58_address=validator_ss58_address)
        verified = keypair.verify(signed_data, signature)
    except Exception:
        raise NotAuthenticated("ss58 address invalid")

    if not verified:
        raise NotAuthenticated("Signature invalid")

    try:
        validator = Validator.objects.get(ss58_address=validator_ss58_address)
    except Validator.DoesNotExist:
        raise NotAuthenticated("Validator unknown")

    if not validator.is_active:
        raise NotAuthenticated("Validator inactive")

    return validator.id


class ValidatorSystemEventView(APIView):
    def post(self, request, *args, validator_ss58_address, **kwargs):
        validator_id = get_validator_id(request, validator_ss58_address)

        for item in request.data:
            item["validator"] = validator_id
            item["timestamp"] = datetime.datetime.fromisoformat(item["timestamp"])

        serializer = ValidatorSystemEventSerializer(data=request.data, many=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
