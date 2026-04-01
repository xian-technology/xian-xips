import datetime
import unittest
from pathlib import Path

from contracting.client import ContractingClient
from contracting.stdlib.bridge.hashing import sha3
from xian_py.wallet import Wallet
from xian_runtime_types.time import Datetime


TOKEN_CODE = """
approvals = Hash(default_value=0)
metadata = Hash()

ApproveEvent = LogEvent(
    "Approve",
    {
        "from": indexed(str),
        "to": indexed(str),
        "amount": (int, float, decimal),
    },
)

@construct
def seed():
    metadata["permit_authorizer"] = "permit_authorizer"

@export
def approve_from_authorizer(owner: str, spender: str, amount: float):
    authorizer = metadata["permit_authorizer"] or "permit_authorizer"
    assert ctx.caller == authorizer, "Only permit authorizer can approve on behalf of others."
    assert amount >= 0, "Cannot approve negative balances."
    approvals[owner, spender] = amount
    ApproveEvent({"from": owner, "to": spender, "amount": amount})
"""


class TestXSC002PermitAuthorizer(unittest.TestCase):
    def setUp(self):
        self.chain_id = "test-chain"
        self.client = ContractingClient(environment={"chain_id": self.chain_id})
        self.client.flush()

        contract_path = Path(__file__).parent.parent / "XSC0002.py"
        self.client.submit(TOKEN_CODE, name="con_token")
        self.client.submit(contract_path.read_text(), name="permit_authorizer")

        self.token = self.client.get_contract("con_token")
        self.authorizer = self.client.get_contract("permit_authorizer")

    def tearDown(self):
        self.client.flush()

    def construct_permit_msg(
        self,
        token_contract: str,
        owner: str,
        spender: str,
        value: float,
        deadline: str,
    ):
        return (
            f"{token_contract}:{owner}:{spender}:{value}:{deadline}:"
            f"permit_authorizer:{self.chain_id}"
        )

    def create_deadline(self, minutes=1):
        d = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        return Datetime(d.year, d.month, d.day, hour=d.hour, minute=d.minute)

    def test_valid_permit_sets_token_approval(self):
        wallet = Wallet(
            "ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8"
        )
        owner = wallet.public_key
        spender = "some_spender"
        deadline = str(self.create_deadline())
        value = 100
        msg = self.construct_permit_msg(
            "con_token",
            owner,
            spender,
            value,
            deadline,
        )
        permit_hash = sha3(msg)
        signature = wallet.sign_msg(msg)

        response = self.authorizer.permit(
            token_contract="con_token",
            owner=owner,
            spender=spender,
            value=value,
            deadline=deadline,
            signature=signature,
        )

        self.assertEqual(response, permit_hash)
        self.assertEqual(self.authorizer.permits[permit_hash], True)
        self.assertEqual(self.token.approvals[owner, spender], value)

    def test_expired_permit_fails(self):
        wallet = Wallet(
            "ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8"
        )
        owner = wallet.public_key
        spender = "some_spender"
        deadline = self.create_deadline(minutes=-1)
        value = 100
        msg = self.construct_permit_msg(
            "con_token",
            owner,
            spender,
            value,
            str(deadline),
        )
        signature = wallet.sign_msg(msg)

        with self.assertRaises(Exception) as context:
            self.authorizer.permit(
                token_contract="con_token",
                owner=owner,
                spender=spender,
                value=value,
                deadline=str(deadline),
                signature=signature,
            )

        self.assertIn("Permit has expired", str(context.exception))

    def test_invalid_signature_fails(self):
        wallet = Wallet(
            "ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8"
        )
        owner = wallet.public_key
        spender = "some_spender"
        deadline = str(self.create_deadline())
        value = 100
        msg = self.construct_permit_msg(
            "con_token",
            owner,
            spender,
            value,
            deadline,
        )
        signature = wallet.sign_msg(msg + ":tampered")

        with self.assertRaises(Exception) as context:
            self.authorizer.permit(
                token_contract="con_token",
                owner=owner,
                spender=spender,
                value=value,
                deadline=deadline,
                signature=signature,
            )

        self.assertIn("Invalid signature", str(context.exception))

    def test_permit_hash_cannot_be_reused(self):
        wallet = Wallet(
            "ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8"
        )
        owner = wallet.public_key
        spender = "some_spender"
        deadline = str(self.create_deadline())
        value = 100
        msg = self.construct_permit_msg(
            "con_token",
            owner,
            spender,
            value,
            deadline,
        )
        signature = wallet.sign_msg(msg)

        self.authorizer.permit(
            token_contract="con_token",
            owner=owner,
            spender=spender,
            value=value,
            deadline=deadline,
            signature=signature,
        )

        with self.assertRaises(Exception) as context:
            self.authorizer.permit(
                token_contract="con_token",
                owner=owner,
                spender=spender,
                value=value,
                deadline=deadline,
                signature=signature,
            )

        self.assertIn("Permit can only be used once", str(context.exception))
