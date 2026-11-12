permits = Hash()
nonces = Hash(default_value=0)

NEWLINE = chr(10)

TOKEN_PERMIT_INTERFACE = [
    importlib.Func(
        "approve_from_authorizer",
        args=("owner", "spender", "amount"),
    ),
]


def parse_time(value: str):
    return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def require_text(value: str, label: str):
    assert isinstance(value, str) and value != "", label + " is required."
    return value


def canonical_amount(value: Any):
    assert not isinstance(value, bool), "Permit amount must not be boolean."
    amount = decimal(str(value))
    assert amount >= 0, "Cannot approve negative balances."
    return amount


def require_token(token_contract: str):
    assert importlib.exists(token_contract), "Token contract does not exist."
    assert importlib.enforce_interface(token_contract, TOKEN_PERMIT_INTERFACE), (
        "Token contract does not satisfy the permit authorizer interface."
    )
    return importlib.import_module(token_contract)


@export
def permit(
    token_contract: str,
    owner: str,
    spender: str,
    value: Any,
    deadline: str,
    nonce: int,
    signature: str,
):
    token_contract = require_text(token_contract, "token_contract")
    owner = require_text(owner, "owner")
    spender = require_text(spender, "spender")
    deadline = require_text(deadline, "deadline")
    assert isinstance(nonce, int), "nonce must be an integer."
    assert nonce >= 0, "nonce must be non-negative."

    deadline_time = parse_time(deadline)
    amount = canonical_amount(value)
    current_nonce = nonces[owner]
    assert nonce == current_nonce, "Invalid permit nonce."
    permit_msg = construct_permit_msg(
        token_contract=token_contract,
        owner=owner,
        spender=spender,
        amount=amount,
        deadline=str(deadline_time),
        nonce=nonce,
    )
    permit_hash = hashlib.sha3_text(permit_msg)

    assert permits[permit_hash] is None, "Permit can only be used once."
    assert now < deadline_time, "Permit has expired."
    assert crypto.verify(owner, permit_msg, signature), "Invalid signature."

    token = require_token(token_contract)
    nonces[owner] = current_nonce + 1
    permits[permit_hash] = True
    token.approve_from_authorizer(
        owner=owner,
        spender=spender,
        amount=amount,
    )

    return permit_hash


def construct_permit_msg(
    token_contract: str,
    owner: str,
    spender: str,
    amount: Any,
    deadline: str,
    nonce: int,
):
    return (
        "xian-permit-v2"
        + NEWLINE
        + "chain_id:"
        + chain_id
        + NEWLINE
        + "authorizer:"
        + ctx.this
        + NEWLINE
        + "token_contract:"
        + token_contract
        + NEWLINE
        + "owner:"
        + owner
        + NEWLINE
        + "spender:"
        + spender
        + NEWLINE
        + "amount:"
        + str(amount)
        + NEWLINE
        + "deadline:"
        + deadline
        + NEWLINE
        + "nonce:"
        + str(nonce)
    )
