import uuid
from datetime import UTC, datetime

import bittensor
from compute_horde.executor_class import DEFAULT_EXECUTOR_CLASS
from compute_horde.mv_protocol.validator_requests import ReceiptPayload
from compute_horde.receipts import Receipt

miner_wallet = bittensor.wallet(name="test_wallet_miner")
miner_wallet.create_if_non_existent(coldkey_use_password=False, hotkey_use_password=False)
miner_hotkey = miner_wallet.get_hotkey()

validator_wallet = bittensor.wallet(name="test_wallet_validator")
validator_wallet.create_if_non_existent(coldkey_use_password=False, hotkey_use_password=False)
validator_hotkey = validator_wallet.get_hotkey()

receipt_payload = ReceiptPayload(
    job_uuid=str(uuid.uuid4()),
    miner_hotkey=miner_hotkey.ss58_address,
    validator_hotkey=validator_hotkey.ss58_address,
    time_started=datetime.now(tz=UTC),
    time_took_us=30_000_000,
    score_str="0.1234",
    executor_class=DEFAULT_EXECUTOR_CLASS,
)

receipt_payload_blob = receipt_payload.blob_for_signing()
miner_signature = f"0x{miner_hotkey.sign(receipt_payload_blob).hex()}"
validator_signature = f"0x{validator_hotkey.sign(receipt_payload_blob).hex()}"

receipt = Receipt(
    payload=receipt_payload,
    miner_signature=miner_signature,
    validator_signature=validator_signature,
)
receipt_json = receipt.model_dump_json()
print(receipt_json)
