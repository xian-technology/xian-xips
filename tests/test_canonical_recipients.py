"""Public-key case mistakes must not create permanently unreachable holdings."""

import os
from pathlib import Path

import pytest
from contracting.local import ContractingClient

ROOT = Path(
    os.environ.get("XIAN_RECIPIENT_SOURCE_ROOT", Path(__file__).resolve().parents[1])
)
FUNGIBLE_SOURCES = [
    "XSC001_standard_token/XSC001.py",
    "XSC003_streaming_token/XSC0003.py",
    "XSC004_wrapped_token/XSC0004.py",
    "XSC004_wrapped_token/bridge_template.py",
]
BAD_RECIPIENTS = ["AB" * 32, "aB" * 32]


@pytest.fixture(params=FUNGIBLE_SOURCES)
def token(request):
    client = ContractingClient()
    client.flush()
    client.submit((ROOT / request.param).read_text(), name="con_token")
    proxy = client.get_contract_proxy("con_token")
    if request.param.endswith("bridge_template.py"):
        proxy.mint(amount=1000, to="sys", signer="sys")
    yield proxy
    client.flush()


@pytest.mark.parametrize("recipient", BAD_RECIPIENTS)
def test_transfer_rejects_noncanonical_key_without_losing_tokens(token, recipient):
    before = token.balance_of(address="sys")
    with pytest.raises(AssertionError, match="canonical lowercase"):
        token.transfer(amount=10, to=recipient, signer="sys")
    assert token.balance_of(address="sys") == before
    assert token.balance_of(address=recipient) == 0


def test_delegated_transfer_preserves_approval_on_bad_recipient(token):
    token.approve(amount=10, to="con_spender", signer="sys")
    with pytest.raises(AssertionError, match="canonical lowercase"):
        token.transfer_from(
            amount=10, to=BAD_RECIPIENTS[0], main_account="sys", signer="con_spender"
        )
    assert token.approvals["sys", "con_spender"] == 10
    assert token.balance_of(address=BAD_RECIPIENTS[0]) == 0


@pytest.mark.parametrize("recipient", ["ab" * 32, "con_vault", "con_" + "A" * 60])
def test_transfer_keeps_canonical_keys_and_contract_names_usable(token, recipient):
    token.transfer(amount=10, to=recipient, signer="sys")
    assert token.balance_of(address=recipient) == 10


def test_approval_does_not_target_a_noncanonical_public_key(token):
    with pytest.raises(AssertionError, match="canonical lowercase"):
        token.approve(amount=10, to=BAD_RECIPIENTS[0], signer="sys")


@pytest.mark.parametrize("source", FUNGIBLE_SOURCES[1:3])
def test_metadata_operator_cannot_be_lost_to_a_noncanonical_key(source):
    client = ContractingClient()
    client.flush()
    try:
        client.submit((ROOT / source).read_text(), name="con_token")
        proxy = client.get_contract_proxy("con_token")
        with pytest.raises(AssertionError, match="canonical lowercase"):
            proxy.change_metadata(key="operator", value=BAD_RECIPIENTS[0], signer="sys")
        proxy.change_metadata(key="token_name", value="Still governed", signer="sys")
        assert proxy.metadata["token_name"] == "Still governed"
    finally:
        client.flush()


@pytest.mark.parametrize("source", FUNGIBLE_SOURCES[2:])
def test_mint_rejects_noncanonical_recipient_without_changing_supply(source):
    client = ContractingClient()
    client.flush()
    try:
        client.submit((ROOT / source).read_text(), name="con_wrapped")
        wrapped = client.get_contract_proxy("con_wrapped")
        before = wrapped.metadata["total_supply"]
        with pytest.raises(AssertionError, match="canonical lowercase"):
            wrapped.mint(amount=10, to=BAD_RECIPIENTS[0], signer="sys")
        assert wrapped.metadata["total_supply"] == before
        assert wrapped.balance_of(address=BAD_RECIPIENTS[0]) == 0
    finally:
        client.flush()


@pytest.mark.parametrize("source", FUNGIBLE_SOURCES[2:])
def test_minter_role_cannot_be_lost_to_a_noncanonical_key(source):
    client = ContractingClient()
    client.flush()
    try:
        client.submit((ROOT / source).read_text(), name="con_wrapped")
        wrapped = client.get_contract_proxy("con_wrapped")
        with pytest.raises(AssertionError, match="canonical lowercase"):
            wrapped.change_minter(new_minter=BAD_RECIPIENTS[0], signer="sys")
        wrapped.mint(amount=10, to="con_vault", signer="sys")
        assert wrapped.balance_of(address="con_vault") == 10
    finally:
        client.flush()


def test_nft_mint_rejects_noncanonical_owner_without_creating_a_token():
    client = ContractingClient()
    client.flush()
    try:
        client.submit(
            "@export\ndef transfer_from(amount: decimal, to: str, main_account: str):\n    pass\n",
            name="currency",
        )
        source = ROOT / "XSC005_non_fungible_token/XSC0005_nft.py"
        client.submit(source.read_text(), name="con_nft")
        nft = client.get_contract_proxy("con_nft")
        with pytest.raises(AssertionError, match="canonical lowercase"):
            nft.mint(
                token_id="test",
                to=BAD_RECIPIENTS[0],
                name="Test",
                description="",
                mime_type="text/plain",
                encoding="utf8",
                content="test",
                signer="sys",
            )
        assert not nft.exists(token_id="test")
    finally:
        client.flush()
