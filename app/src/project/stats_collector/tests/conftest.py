import pytest
import pytest_asyncio
from bittensor import Keypair

from ...core.models import Validator


@pytest.fixture
def keypair():
    return Keypair.create_from_mnemonic("slot excuse valid grief praise rifle spoil auction weasel glove pen share")


@pytest.fixture
def other_keypair():
    return Keypair.create_from_mnemonic("lion often fade hover duty debris write tumble shock ask bracket roast")


@pytest_asyncio.fixture
async def validator(db, keypair):
    return await Validator.objects.acreate(ss58_address=keypair.ss58_address, is_active=True)
