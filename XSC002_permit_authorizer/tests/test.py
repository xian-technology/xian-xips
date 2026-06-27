import datetime
import hashlib
import unittest
from decimal import Decimal
from pathlib import Path

from contracting.local import ContractingClient
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

        self.token = self.client.get_contract_proxy("con_token")
        self.authorizer = self.client.get_contract_proxy("permit_authorizer")

    def tearDown(self):
        self.client.flush()

    def construct_permit_msg(
        self,
        token_contract: str,
        owner: str,
        spender: str,
        value,
        deadline: str,
        nonce: int,
    ):
        amount = Decimal(str(value))
        amount_text = format(amount.normalize(), "f")
        if "." in amount_text:
            amount_text = amount_text.rstrip("0").rstrip(".")
        return "\n".join(
            [
                "xian-permit-v2",
                f"chain_id:{self.chain_id}",
                "authorizer:permit_authorizer",
                f"token_contract:{token_contract}",
                f"owner:{owner}",
                f"spender:{spender}",
                f"amount:{amount_text}",
                f"deadline:{deadline}",
                f"nonce:{nonce}",
            ]
        )

    def permit_hash(self, msg: str):
        return hashlib.sha3_256(msg.encode("utf-8")).hexdigest()

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
            nonce=0,
        )
        permit_hash = self.permit_hash(msg)
        signature = wallet.sign_msg(msg)

        response = self.authorizer.permit(
            token_contract="con_token",
            owner=owner,
            spender=spender,
            value=value,
            deadline=deadline,
            nonce=0,
            signature=signature,
        )

        self.assertEqual(response, permit_hash)
        self.assertEqual(self.authorizer.permits[permit_hash], True)
        self.assertEqual(self.token.approvals[owner, spender], value)
        self.assertEqual(self.authorizer.nonces[owner], 1)

    def test_valid_permit_round_amounts(self):
        # Regression: round amounts (>= 1000) whose decimal normalizes with a
        # positive exponent used to be rendered by str(decimal(...)) as
        # engineering notation ("1E+6"), which never matched the plain-decimal
        # "amount:1000000" the payer signs, so every such permit was rejected.
        wallet = Wallet(
            "ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8"
        )
        owner = wallet.public_key
        spender = "some_spender"
        deadline = str(self.create_deadline())

        for nonce, value in enumerate((1000, 12000, 1000000, 2500000)):
            msg = self.construct_permit_msg(
                "con_token",
                owner,
                spender,
                value,
                deadline,
                nonce=nonce,
            )
            signature = wallet.sign_msg(msg)

            self.authorizer.permit(
                token_contract="con_token",
                owner=owner,
                spender=spender,
                value=value,
                deadline=deadline,
                nonce=nonce,
                signature=signature,
            )

            self.assertEqual(self.token.approvals[owner, spender], value)
            self.assertEqual(self.authorizer.nonces[owner], nonce + 1)

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
            nonce=0,
        )
        signature = wallet.sign_msg(msg)

        with self.assertRaises(Exception) as context:
            self.authorizer.permit(
                token_contract="con_token",
                owner=owner,
                spender=spender,
                value=value,
                deadline=str(deadline),
                nonce=0,
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
            nonce=0,
        )
        signature = wallet.sign_msg(msg + ":tampered")

        with self.assertRaises(Exception) as context:
            self.authorizer.permit(
                token_contract="con_token",
                owner=owner,
                spender=spender,
                value=value,
                deadline=deadline,
                nonce=0,
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
            nonce=0,
        )
        signature = wallet.sign_msg(msg)

        self.authorizer.permit(
            token_contract="con_token",
            owner=owner,
            spender=spender,
            value=value,
            deadline=deadline,
            nonce=0,
            signature=signature,
        )

        with self.assertRaises(Exception) as context:
            self.authorizer.permit(
                token_contract="con_token",
                owner=owner,
                spender=spender,
                value=value,
                deadline=deadline,
                nonce=0,
                signature=signature,
            )

        self.assertIn("Invalid permit nonce", str(context.exception))
