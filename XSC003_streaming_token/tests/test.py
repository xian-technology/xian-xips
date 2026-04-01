import datetime
import unittest
from pathlib import Path

from contracting.client import ContractingClient
from xian_runtime_types.time import Datetime


class TestXSC003StreamingToken(unittest.TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()

        contract_path = Path(__file__).parent.parent / "XSC0003.py"
        self.client.submit(contract_path.read_text(), name="currency")
        self.currency = self.client.get_contract("currency")

    def tearDown(self):
        self.client.flush()

    def create_date(self, year, month, day, hour=0, minute=0):
        d = datetime.datetime(year, month, day, hour, minute)
        return Datetime(d.year, d.month, d.day, hour=d.hour, minute=d.minute)

    def test_initial_balance(self):
        self.assertEqual(self.currency.balances["sys"], 1_000_000)

    def test_approve_and_transfer_from_use_approvals(self):
        self.currency.approve(amount=200, to="bob", signer="sys")
        self.currency.transfer_from(
            amount=100,
            to="bob",
            main_account="sys",
            signer="bob",
        )

        self.assertEqual(self.currency.balances["bob"], 100)
        self.assertEqual(self.currency.approvals["sys", "bob"], 100)

    def test_create_stream_success(self):
        sender = "alice"
        receiver = "bob"
        begins = self.create_date(2023, 1, 1)
        closes = self.create_date(2023, 12, 31)

        stream_id = self.currency.create_stream(
            receiver=receiver,
            rate=10,
            begins=str(begins),
            closes=str(closes),
            signer=sender,
        )

        self.assertEqual(self.currency.streams[stream_id, "status"], "active")
        self.assertEqual(self.currency.streams[stream_id, "sender"], sender)
        self.assertEqual(self.currency.streams[stream_id, "receiver"], receiver)
        self.assertEqual(self.currency.streams[stream_id, "rate"], 10)
        self.assertEqual(self.currency.streams[stream_id, "claimed"], 0)

    def test_balance_stream_transfers_due_amount(self):
        sender = "alice"
        receiver = "bob"
        begins = self.create_date(2023, 1, 1)
        closes = self.create_date(2023, 1, 1, hour=1)
        self.currency.balances[sender] = 3600

        stream_id = self.currency.create_stream(
            receiver=receiver,
            rate=1,
            begins=str(begins),
            closes=str(closes),
            signer=sender,
        )

        self.currency.balance_stream(
            stream_id=stream_id,
            signer=receiver,
            environment={"now": closes},
        )

        self.assertEqual(self.currency.balances[receiver], 3600)
        self.assertEqual(self.currency.balances[sender], 0)
        self.assertEqual(self.currency.streams[stream_id, "claimed"], 3600)

    def test_finalize_stream_requires_zero_outstanding_balance(self):
        sender = "alice"
        receiver = "bob"
        begins = self.create_date(2023, 1, 1)
        closes = self.create_date(2023, 1, 1, hour=1)
        self.currency.balances[sender] = 3600

        stream_id = self.currency.create_stream(
            receiver=receiver,
            rate=1,
            begins=str(begins),
            closes=str(closes),
            signer=sender,
        )

        with self.assertRaises(Exception):
            self.currency.finalize_stream(
                stream_id=stream_id,
                signer=sender,
                environment={"now": closes},
            )

        self.currency.balance_stream(
            stream_id=stream_id,
            signer=receiver,
            environment={"now": closes},
        )
        self.currency.finalize_stream(
            stream_id=stream_id,
            signer=sender,
            environment={"now": closes},
        )

        self.assertEqual(self.currency.streams[stream_id, "status"], "finalized")

    def test_change_close_time_clamps_to_begin(self):
        sender = "alice"
        begins = self.create_date(2023, 1, 10)
        closes = self.create_date(2023, 1, 20)
        earlier = self.create_date(2023, 1, 5)

        stream_id = self.currency.create_stream(
            receiver="bob",
            rate=1,
            begins=str(begins),
            closes=str(closes),
            signer=sender,
        )

        self.currency.change_close_time(
            stream_id=stream_id,
            new_close_time=str(earlier),
            signer=sender,
            environment={"now": self.create_date(2023, 1, 1)},
        )

        self.assertEqual(self.currency.streams[stream_id, "closes"], begins)

    def test_receiver_can_forfeit_stream(self):
        sender = "alice"
        receiver = "bob"
        begins = self.create_date(2023, 1, 1)
        closes = self.create_date(2023, 1, 2)

        stream_id = self.currency.create_stream(
            receiver=receiver,
            rate=1,
            begins=str(begins),
            closes=str(closes),
            signer=sender,
        )

        now = self.create_date(2023, 1, 1, hour=12)
        self.currency.forfeit_stream(
            stream_id=stream_id,
            signer=receiver,
            environment={"now": now},
        )

        self.assertEqual(self.currency.streams[stream_id, "status"], "forfeit")
        self.assertEqual(self.currency.streams[stream_id, "closes"], now)
