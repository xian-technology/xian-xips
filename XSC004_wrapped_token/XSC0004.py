balances = Hash(default_value=0)
approvals = Hash(default_value=0)
metadata = Hash()
withdrawal_count = Variable()

minter = Variable()

MAX_DESTINATION_CHAIN_LENGTH = 64
MAX_DESTINATION_ADDRESS_LENGTH = 256
MAX_MEMO_LENGTH = 256


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
MintEvent = LogEvent(
    "Mint",
    {
        "to": indexed(str),
        "amount": (int, float, decimal),
    },
)
BurnEvent = LogEvent(
    "Burn",
    {
        "from": indexed(str),
        "amount": (int, float, decimal),
        "destination_chain": indexed(str),
        "destination_address": str,
        "withdrawal_id": indexed(str),
        "memo": str,
    },
)

@construct
def seed():
    balances[ctx.caller] = 1_000_000

    metadata["token_name"] = "TEST TOKEN"
    metadata["token_symbol"] = "TST"
    metadata["token_logo_url"] = "https://some.token.url/test-token.png"
    metadata["token_website"] = "https://some.token.url"
    metadata["total_supply"] = balances[ctx.caller]
    metadata["operator"] = ctx.caller

    minter.set(ctx.caller)
    withdrawal_count.set(0)


def require_text(value: str, field_name: str, max_length: int):
    assert isinstance(value, str), field_name + " must be a string."

    normalized = value.strip()
    assert normalized != "", field_name + " must be non-empty."
    assert len(normalized) <= max_length, field_name + " is too long."

    return normalized


def normalize_memo(memo: str):
    if memo is None:
        return ""

    assert isinstance(memo, str), "memo must be a string."
    assert len(memo) <= MAX_MEMO_LENGTH, "memo is too long."

    return memo


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
def change_minter(new_minter: str):
    assert ctx.caller == minter.get(), "Only minter can change minter."
    minter.set(new_minter)


@export
def mint(amount: float, to: str):
    assert ctx.caller == minter.get(), "Only minter can mint tokens."
    assert amount > 0, "Cannot mint negative balances."

    balances[to] += amount
    metadata["total_supply"] += amount

    MintEvent({"to": to, "amount": amount})


@export
def burn(
    amount: float,
    destination_chain: str,
    destination_address: str,
    memo: str = "",
):
    assert amount > 0, "Cannot burn negative balances."
    assert balances[ctx.caller] >= amount, "Not enough coins to burn."

    destination_chain = require_text(
        destination_chain,
        "destination_chain",
        MAX_DESTINATION_CHAIN_LENGTH,
    )
    destination_address = require_text(
        destination_address,
        "destination_address",
        MAX_DESTINATION_ADDRESS_LENGTH,
    )
    memo = normalize_memo(memo)

    withdrawal_nonce = withdrawal_count.get()
    withdrawal_id = ctx.this + ":" + str(withdrawal_nonce)

    balances[ctx.caller] -= amount
    metadata["total_supply"] -= amount
    withdrawal_count.set(withdrawal_nonce + 1)

    BurnEvent(
        {
            "from": ctx.caller,
            "amount": amount,
            "destination_chain": destination_chain,
            "destination_address": destination_address,
            "withdrawal_id": withdrawal_id,
            "memo": memo,
        }
    )

    return withdrawal_id
