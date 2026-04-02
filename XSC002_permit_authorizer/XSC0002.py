permits = Hash()

TOKEN_PERMIT_INTERFACE = [
    importlib.Func(
        "approve_from_authorizer",
        args=("owner", "spender", "amount"),
    ),
]


def parse_time(value: str):
    return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


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
    value: float,
    deadline: str,
    signature: str,
):
    deadline_time = parse_time(deadline)
    permit_msg = construct_permit_msg(
        token_contract=token_contract,
        owner=owner,
        spender=spender,
        value=value,
        deadline=str(deadline_time),
    )
    permit_hash = hashlib.sha3(permit_msg)

    assert permits[permit_hash] is None, "Permit can only be used once."
    assert now < deadline_time, "Permit has expired."
    assert value >= 0, "Cannot approve negative balances."
    assert crypto.verify(owner, permit_msg, signature), "Invalid signature."

    token = require_token(token_contract)
    token.approve_from_authorizer(
        owner=owner,
        spender=spender,
        amount=value,
    )

    permits[permit_hash] = True
    return permit_hash


def construct_permit_msg(
    token_contract: str,
    owner: str,
    spender: str,
    value: float,
    deadline: str,
):
    return (
        f"{token_contract}:{owner}:{spender}:{value}:{deadline}:{ctx.this}:{chain_id}"
    )
