import unittest
from pathlib import Path

from contracting.client import ContractingClient


class TestXSC001Token(unittest.TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()

        contract_path = Path(__file__).parent.parent / "XSC001.py"
        self.client.submit(contract_path.read_text(), name="currency")
        self.currency = self.client.get_contract("currency")

    def tearDown(self):
        self.client.flush()

    def test_initial_balance(self):
        self.assertEqual(self.currency.balances["sys"], 1_000_000)

    def test_transfer(self):
        self.currency.transfer(amount=100, to="bob", signer="sys")

        self.assertEqual(self.currency.balances["bob"], 100)
        self.assertEqual(self.currency.balances["sys"], 999_900)

    def test_change_metadata_requires_operator(self):
        with self.assertRaises(Exception):
            self.currency.change_metadata(
                key="token_name",
                value="NEW TOKEN",
                signer="bob",
            )

        self.currency.change_metadata(
            key="token_name",
            value="NEW TOKEN",
            signer="sys",
        )
        self.assertEqual(self.currency.metadata["token_name"], "NEW TOKEN")

    def test_approve_uses_approvals_hash(self):
        self.currency.approve(amount=500, to="eve", signer="sys")
        self.assertEqual(self.currency.approvals["sys", "eve"], 500)

    def test_transfer_from_consumes_approval(self):
        self.currency.approve(amount=200, to="bob", signer="sys")
        self.currency.transfer_from(
            amount=100,
            to="bob",
            main_account="sys",
            signer="bob",
        )

        self.assertEqual(self.currency.balances["bob"], 100)
        self.assertEqual(self.currency.balances["sys"], 999_900)
        self.assertEqual(self.currency.approvals["sys", "bob"], 100)

    def test_approve_overwrites_previous_allowance(self):
        self.currency.approve(amount=500, to="eve", signer="sys")
        self.currency.approve(amount=200, to="eve", signer="sys")

        self.assertEqual(self.currency.approvals["sys", "eve"], 200)
