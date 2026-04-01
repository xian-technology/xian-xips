balances = Hash(default_value=0)
approvals = Hash(default_value=0)
metadata = Hash()
streams = Hash()

TransferEvent = LogEvent(
    "Transfer",
    {
        "from": indexed(str),
        "to": indexed(str),
        "amount": (int, float, decimal),
    },
)
ApproveEvent = LogEvent(
    "Approve",
    {
        "from": indexed(str),
        "to": indexed(str),
        "amount": (int, float, decimal),
    },
)
StreamCreatedEvent = LogEvent(
    "StreamCreated",
    {
        "sender": indexed(str),
        "receiver": indexed(str),
        "stream_id": indexed(str),
        "rate": (int, float, decimal),
        "begins": str,
        "closes": str,
    },
)
StreamBalanceEvent = LogEvent(
    "StreamBalance",
    {
        "receiver": indexed(str),
        "sender": indexed(str),
        "stream_id": indexed(str),
        "amount": (int, float, decimal),
        "balancer": str,
    },
)
StreamCloseChangeEvent = LogEvent(
    "StreamCloseChange",
    {
        "receiver": indexed(str),
        "sender": indexed(str),
        "stream_id": indexed(str),
        "time": str,
    },
)
StreamForfeitEvent = LogEvent(
    "StreamForfeit",
    {
        "receiver": indexed(str),
        "sender": indexed(str),
        "stream_id": indexed(str),
        "time": str,
    },
)
StreamFinalizedEvent = LogEvent(
    "StreamFinalized",
    {
        "receiver": indexed(str),
        "sender": indexed(str),
        "stream_id": indexed(str),
        "time": str,
    },
)

SENDER_KEY = "sender"
RECEIVER_KEY = "receiver"
STATUS_KEY = "status"
BEGIN_KEY = "begins"
CLOSE_KEY = "closes"
RATE_KEY = "rate"
CLAIMED_KEY = "claimed"
STREAM_ACTIVE = "active"
STREAM_FINALIZED = "finalized"
STREAM_FORFEIT = "forfeit"


@construct
def seed():
    balances[ctx.caller] = 1_000_000

    metadata["token_name"] = "TEST TOKEN"
    metadata["token_symbol"] = "TST"
    metadata["token_logo_url"] = "https://some.token.url/test-token.png"
    metadata["token_website"] = "https://some.token.url"
    metadata["total_supply"] = balances[ctx.caller]
    metadata["operator"] = ctx.caller


@export
def change_metadata(key: str, value: Any):
    assert ctx.caller == metadata["operator"], "Only operator can set metadata."
    metadata[key] = value


@export
def transfer(amount: float, to: str):
    assert amount > 0, "Cannot send negative balances."
    assert balances[ctx.caller] >= amount, "Not enough coins to send."

    balances[ctx.caller] -= amount
    balances[to] += amount

    TransferEvent({"from": ctx.caller, "to": to, "amount": amount})


@export
def approve(amount: float, to: str):
    assert amount >= 0, "Cannot approve negative balances."
    approvals[ctx.caller, to] = amount

    ApproveEvent({"from": ctx.caller, "to": to, "amount": amount})


@export
def transfer_from(amount: float, to: str, main_account: str):
    assert amount > 0, "Cannot send negative balances."
    assert (
        approvals[main_account, ctx.caller] >= amount
    ), f"Not enough coins approved to send. You have {approvals[main_account, ctx.caller]} and are trying to spend {amount}"
    assert balances[main_account] >= amount, "Not enough coins to send."

    approvals[main_account, ctx.caller] -= amount
    balances[main_account] -= amount
    balances[to] += amount

    TransferEvent({"from": main_account, "to": to, "amount": amount})


@export
def balance_of(address: str):
    return balances[address]


@export
def create_stream(receiver: str, rate: float, begins: str, closes: str):
    begins = strptime_ymdhms(begins)
    closes = strptime_ymdhms(closes)
    sender = ctx.caller

    stream_id = perform_create_stream(sender, receiver, rate, begins, closes)
    return stream_id


def perform_create_stream(
    sender: str,
    receiver: str,
    rate: float,
    begins: datetime.datetime,
    closes: datetime.datetime,
):
    stream_id = hashlib.sha3(f"{sender}:{receiver}:{begins}:{closes}:{rate}")

    assert streams[stream_id, STATUS_KEY] is None, "Stream already exists."
    assert begins < closes, "Stream cannot begin after the close date."
    assert rate > 0, "Rate must be greater than 0."

    streams[stream_id, STATUS_KEY] = STREAM_ACTIVE
    streams[stream_id, BEGIN_KEY] = begins
    streams[stream_id, CLOSE_KEY] = closes
    streams[stream_id, RECEIVER_KEY] = receiver
    streams[stream_id, SENDER_KEY] = sender
    streams[stream_id, RATE_KEY] = rate
    streams[stream_id, CLAIMED_KEY] = 0

    StreamCreatedEvent(
        {
            "sender": sender,
            "receiver": receiver,
            "stream_id": stream_id,
            "rate": rate,
            "begins": str(begins),
            "closes": str(closes),
        }
    )

    return stream_id


@export
def balance_stream(stream_id: str):
    assert streams[stream_id, STATUS_KEY], "Stream does not exist."
    assert (
        streams[stream_id, STATUS_KEY] == STREAM_ACTIVE
    ), "You can only balance active streams."
    assert now > streams[stream_id, BEGIN_KEY], "Stream has not started yet."

    sender = streams[stream_id, SENDER_KEY]
    receiver = streams[stream_id, RECEIVER_KEY]

    assert ctx.caller in [sender, receiver], "Only sender or receiver can balance a stream."

    closes = streams[stream_id, CLOSE_KEY]
    begins = streams[stream_id, BEGIN_KEY]
    rate = streams[stream_id, RATE_KEY]
    claimed = streams[stream_id, CLAIMED_KEY]

    outstanding_balance = calc_outstanding_balance(begins, closes, rate, claimed)
    assert outstanding_balance > 0, "No amount due on this stream."

    claimable_amount = calc_claimable_amount(outstanding_balance, sender)

    balances[sender] -= claimable_amount
    balances[receiver] += claimable_amount
    streams[stream_id, CLAIMED_KEY] += claimable_amount

    StreamBalanceEvent(
        {
            "receiver": receiver,
            "sender": sender,
            "stream_id": stream_id,
            "amount": claimable_amount,
            "balancer": ctx.caller,
        }
    )


@export
def change_close_time(stream_id: str, new_close_time: str):
    new_close_time = strptime_ymdhms(new_close_time)

    assert streams[stream_id, STATUS_KEY], "Stream does not exist."
    assert streams[stream_id, STATUS_KEY] == STREAM_ACTIVE, "Stream is not active."

    sender = streams[stream_id, SENDER_KEY]
    receiver = streams[stream_id, RECEIVER_KEY]
    begins = streams[stream_id, BEGIN_KEY]

    assert ctx.caller == sender, "Only sender can change the close time of a stream."

    if new_close_time <= now:
        streams[stream_id, CLOSE_KEY] = now
    elif new_close_time < begins:
        streams[stream_id, CLOSE_KEY] = begins
    else:
        streams[stream_id, CLOSE_KEY] = new_close_time

    StreamCloseChangeEvent(
        {
            "receiver": receiver,
            "sender": sender,
            "stream_id": stream_id,
            "time": str(streams[stream_id, CLOSE_KEY]),
        }
    )


@export
def finalize_stream(stream_id: str):
    assert streams[stream_id, STATUS_KEY], "Stream does not exist."
    assert streams[stream_id, STATUS_KEY] == STREAM_ACTIVE, "Stream is not active."

    sender = streams[stream_id, SENDER_KEY]
    receiver = streams[stream_id, RECEIVER_KEY]

    assert ctx.caller in [sender, receiver], "Only sender or receiver can finalize a stream."

    begins = streams[stream_id, BEGIN_KEY]
    closes = streams[stream_id, CLOSE_KEY]
    rate = streams[stream_id, RATE_KEY]
    claimed = streams[stream_id, CLAIMED_KEY]

    assert closes <= now, "Stream has not closed yet."

    outstanding_balance = calc_outstanding_balance(begins, closes, rate, claimed)
    assert outstanding_balance == 0, "Stream has outstanding balance."

    streams[stream_id, STATUS_KEY] = STREAM_FINALIZED

    StreamFinalizedEvent(
        {
            "receiver": receiver,
            "sender": sender,
            "stream_id": stream_id,
            "time": str(now),
        }
    )


@export
def close_balance_finalize(stream_id: str):
    change_close_time(stream_id=stream_id, new_close_time=str(now))
    balance_finalize(stream_id=stream_id)


@export
def balance_finalize(stream_id: str):
    balance_stream(stream_id=stream_id)
    finalize_stream(stream_id=stream_id)


@export
def forfeit_stream(stream_id: str) -> str:
    assert streams[stream_id, STATUS_KEY], "Stream does not exist."
    assert streams[stream_id, STATUS_KEY] == STREAM_ACTIVE, "Stream is not active."

    receiver = streams[stream_id, RECEIVER_KEY]
    sender = streams[stream_id, SENDER_KEY]

    assert ctx.caller == receiver, "Only receiver can forfeit a stream."

    streams[stream_id, STATUS_KEY] = STREAM_FORFEIT
    streams[stream_id, CLOSE_KEY] = now

    StreamForfeitEvent(
        {
            "receiver": receiver,
            "sender": sender,
            "stream_id": stream_id,
            "time": str(now),
        }
    )


def calc_outstanding_balance(
    begins: datetime.datetime,
    closes: datetime.datetime,
    rate: float,
    claimed: float,
) -> float:
    claimable_end_point = now if now < closes else closes
    claimable_period = claimable_end_point - begins
    claimable_seconds = claimable_period.seconds
    amount_due = (rate * claimable_seconds) - claimed
    return amount_due


def calc_claimable_amount(amount_due: float, sender: str) -> float:
    return amount_due if amount_due < balances[sender] else balances[sender]


def strptime_ymdhms(date_string: str) -> datetime.datetime:
    return datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
