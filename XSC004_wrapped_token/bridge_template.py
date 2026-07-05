# ruff: noqa: F821

balances = Hash(default_value=0)
approvals = Hash(default_value=0)

metadata = Hash()
withdrawal_count = Variable()

operator = Variable()
minter = Variable()

MAX_DESTINATION_CHAIN_LENGTH = 64
MAX_DESTINATION_ADDRESS_LENGTH = 256
MAX_MEMO_LENGTH = 256


TransferEvent = LogEvent(
    event="Transfer",
    params={
        "from": {"type": str, "idx": True},
        "to": {"type": str, "idx": True},
        "amount": {"type": (int, float, decimal)},
    },
)
ApproveEvent = LogEvent(
    event="Approve",
    params={
        "from": {"type": str, "idx": True},
        "to": {"type": str, "idx": True},
        "amount": {"type": (int, float, decimal)},
    },
)
MintEvent = LogEvent(
    event="Mint",
    params={
        "to": {"type": str, "idx": True},
        "amount": {"type": (int, float, decimal)},
    },
)
BurnEvent = LogEvent(
    event="Burn",
    params={
        "from": {"type": str, "idx": True},
        "amount": {"type": (int, float, decimal)},
        "destination_chain": {"type": str, "idx": True},
        "destination_address": {"type": str},
        "withdrawal_id": {"type": str, "idx": True},
        "memo": {"type": str},
    },
)


@construct
def seed():
    metadata["token_name"] = "{{token_name}}"
    metadata["token_symbol"] = "{{token_symbol}}"
    metadata["token_logo_url"] = ""
    metadata["token_logo_svg"] = ""
    metadata["token_website"] = ""
    metadata["total_supply"] = 0

    operator.set(ctx.caller)
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
    assert ctx.caller == operator.get(), "Only operator can set metadata."
    metadata[key] = value


@export
def change_operator(new_operator: str):
    assert ctx.caller == operator.get(), "Only operator can change operator."
    assert isinstance(new_operator, str) and new_operator != "", "new_operator must be non-empty."
    operator.set(new_operator)


@export
def operator_of():
    return operator.get()


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
    approved = approvals[main_account, ctx.caller]

    assert amount > 0, "Cannot send negative balances!"
    assert approved >= amount, f"You approved {approved} but need {amount}"
    assert balances[main_account] >= amount, "Not enough tokens to send!"

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
