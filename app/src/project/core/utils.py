from typing import TYPE_CHECKING

import boto3
import wandb
from constance import config
from django.conf import settings
from structlog import get_logger

if TYPE_CHECKING:
    from bittensor.chain_data import NeuronInfo


log = get_logger(__name__)

s3 = boto3.client(
    service_name="s3",
    endpoint_url=settings.R2_ENDPOINT_URL,
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    region_name=settings.R2_REGION_NAME,
)


def create_signed_upload_url(key: str) -> str:
    """
    Create a signed URL for executor's output.

    https://developers.cloudflare.com/r2/api/s3/presigned-urls/
    """
    # R2: POST, which performs uploads via native HTML forms, is not currently supported.

    # result = s3.generate_presigned_post(
    #     Bucket=settings.R2_BUCKET_NAME,
    #     Key=key,
    #     ExpiresIn=int(expires_in.total_seconds()),
    #     Conditions=[
    #         ['content-length-range', 0, max_content_length],
    #     ],
    # )
    # return result['url'], result['fields']

    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
        },
        ExpiresIn=int(settings.OUTPUT_PRESIGNED_URL_LIFETIME.total_seconds()),
    )


def create_signed_download_url(key: str) -> str:
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
        },
        ExpiresIn=int(settings.DOWNLOAD_PRESIGNED_URL_LIFETIME.total_seconds()),
    )


def upload_data(key: str, data: bytes) -> str:
    s3.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=data,
    )
    return create_signed_download_url(key)


def is_validator(neuron: "NeuronInfo") -> bool:
    if our_validator_address := config.OUR_VALIDATOR_SS58_ADDRESS:
        if neuron.hotkey == our_validator_address:
            return True

    return neuron.stake > 0


def fetch_compute_subnet_hardware() -> dict:
    """
    Retrieve hardware specs for the compute subnet.

    This info is also displayed here: https://opencompute.streamlit.app
    """

    wandb.login(key=settings.WANDB_API_KEY)
    api = wandb.Api()

    # https://github.com/nauttiilus/opencompute/blob/main/main.py
    db_specs_dict = {}
    project_path = "neuralinternet/opencompute"
    runs = api.runs(project_path)
    for run in runs:
        run_config = run.config
        hotkey = run_config.get("hotkey")
        details = run_config.get("specs")
        role = run_config.get("role")
        if hotkey and details and role == "miner":
            db_specs_dict[hotkey] = details

    return db_specs_dict
