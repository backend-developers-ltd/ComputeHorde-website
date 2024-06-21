import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Self

import bittensor
from pydantic import BaseModel, Extra, Field, field_validator
from pydantic_core import to_jsonable_python

if TYPE_CHECKING:
    from bittensor import Keypair


class Error(BaseModel, extra=Extra.allow):
    msg: str
    type: str
    help: str = ""


class Response(BaseModel, extra=Extra.forbid):
    status: Literal["error", "success"]
    errors: list[Error] = []


class AuthenticationRequest(BaseModel, extra=Extra.forbid):
    """Message sent from validator to this app to authenticate itself"""

    message_type: Literal["V0AuthenticationRequest"] = Field(default="V0AuthenticationRequest")
    public_key: str
    signature: str

    @classmethod
    def from_keypair(cls, keypair: "Keypair") -> Self:
        return cls(
            public_key=keypair.public_key.hex(),
            signature=f"0x{keypair.sign(keypair.public_key).hex()}",
        )

    def verify_signature(self) -> bool:
        from bittensor import Keypair

        public_key_bytes = bytes.fromhex(self.public_key)
        keypair = Keypair(public_key=public_key_bytes, ss58_format=42)
        return keypair.verify(public_key_bytes, self.signature)

    @property
    def ss58_address(self) -> str:
        from bittensor import Keypair

        return Keypair(public_key=bytes.fromhex(self.public_key), ss58_format=42).ss58_address


class JobRequest(BaseModel, extra=Extra.forbid):
    """Message sent from this app to validator to request a job execution"""

    type: Literal["job.new"] = Field(
        "job.new"
    )  # this points to a `ValidatorConsumer.job_new` handler (fuck you django-channels!)
    message_type: Literal["V0JobRequest"] = Field(default="V0JobRequest")
    uuid: str
    miner_hotkey: str
    docker_image: str
    raw_script: str
    args: list[str]
    env: dict[str, str]
    use_gpu: bool
    input_url: str
    output_url: str


class Heartbeat(BaseModel, extra=Extra.forbid):
    message_type: Literal["V0Heartbeat"] = Field(default="V0Heartbeat")


class MinerResponse(BaseModel, extra=Extra.allow):
    job_uuid: str
    message_type: str
    docker_process_stderr: str
    docker_process_stdout: str


class JobStatusMetadata(BaseModel, extra=Extra.allow):
    comment: str
    miner_response: MinerResponse | None = None


class JobStatusUpdate(BaseModel, extra=Extra.forbid):
    """
    Message sent from validator to this app in response to NewJobRequest.
    """

    message_type: Literal["V0JobStatusUpdate"] = Field(default="V0JobStatusUpdate")
    uuid: str
    status: Literal["failed", "rejected", "accepted", "completed"]
    metadata: JobStatusMetadata | None = None


class MachineSpecs(BaseModel, extra=Extra.forbid):
    message_type: Literal["V0MachineSpecsUpdate"] = Field(default="V0MachineSpecsUpdate")
    specs: dict
    miner_hotkey: str
    validator_hotkey: str
    batch_id: str | None = None


class ForceDisconnect(BaseModel, extra=Extra.forbid):
    """Message sent when validator is no longer valid and should be disconnected"""

    type: Literal["validator.disconnect"] = Field("validator.disconnect")


class CpuSpec(BaseModel, extra=Extra.forbid):
    model: str | None = None
    count: int
    frequency: Decimal | None = None
    clocks: list[float] | None = None


class GpuDetails(BaseModel, extra=Extra.forbid):
    name: str
    capacity: int | float | None = Field(default=None, description="in MB")
    cuda: str | None = None
    driver: str | None = None
    graphics_speed: int | None = Field(default=None, description="in MHz")
    memory_speed: int | None = Field(default=None, description="in MHz")
    power_limit: float | None = Field(default=None, description="in W")
    uuid: str | None = None
    serial: str | None = None

    @field_validator("power_limit", mode="before")
    @classmethod
    def parse_age(cls, v):
        try:
            return float(v)
        except Exception:
            return None


class GpuSpec(BaseModel, extra=Extra.forbid):
    capacity: int | float | None = None
    count: int | None = None
    details: list[GpuDetails] = []
    graphics_speed: int | None = Field(default=None, description="in MHz")
    memory_speed: int | None = Field(default=None, description="in MHz")


class HardDiskSpec(BaseModel, extra=Extra.forbid):
    total: int | float | None = Field(default=None, description="in kiB")
    free: int | float | None = Field(default=None, description="in kiB")
    used: int | float | None = Field(default=None, description="in kiB")
    read_speed: Decimal | None = None
    write_speed: Decimal | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

    def get_total_gb(self) -> float | None:
        if self.total is None:
            return None
        return self.total / 1024 / 1024


class RamSpec(BaseModel, extra=Extra.forbid):
    total: int | float | None = Field(default=None, description="in kiB")
    free: int | float | None = Field(default=None, description="in kiB")
    available: int | float | None = Field(default=None, description="in kiB")
    used: int | float | None = Field(default=None, description="in kiB")
    read_speed: Decimal | None = None
    write_speed: Decimal | None = None
    swap_free: int | None = Field(default=None, description="in kiB")
    swap_total: int | None = Field(default=None, description="in kiB")
    swap_used: int | None = Field(default=None, description="in kiB")

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

    def get_total_gb(self) -> float | None:
        if self.total is None:
            return None
        return self.total / 1024 / 1024


class HardwareSpec(BaseModel, extra=Extra.allow):
    cpu: CpuSpec
    gpu: GpuSpec | None = None
    hard_disk: HardDiskSpec
    has_docker: bool | None = None
    ram: RamSpec
    virtualization: str | None = None
    os: str | None = None


class ReceiptPayload(BaseModel):
    # Origin of this model may be found in ComputeHorde repo:
    # https://github.com/backend-developers-ltd/ComputeHorde
    # from compute_horde.mv_protocol.validator_requests import ReceiptPayload

    job_uuid: str
    miner_hotkey: str
    validator_hotkey: str
    time_started: datetime
    time_took_us: int  # micro-seconds
    score_str: str

    def blob_for_signing(self) -> str:
        data = to_jsonable_python(self)

        # make time consistent with the format in ComputeHorde
        data["time_started"] = data["time_started"].replace("Z", "+00:00")

        return json.dumps(data, sort_keys=True)

    @property
    def time_took(self) -> timedelta:
        return timedelta(microseconds=self.time_took_us)

    @property
    def score(self) -> float:
        return float(self.score_str)


class Receipt(BaseModel):
    payload: ReceiptPayload
    validator_signature: str
    miner_signature: str

    def verify_miner_signature(self):
        miner_keypair = bittensor.Keypair(ss58_address=self.payload.miner_hotkey)
        return miner_keypair.verify(self.payload.blob_for_signing(), self.miner_signature)

    def verify_validator_signature(self):
        validator_keypair = bittensor.Keypair(ss58_address=self.payload.validator_hotkey)
        return validator_keypair.verify(self.payload.blob_for_signing(), self.validator_signature)
