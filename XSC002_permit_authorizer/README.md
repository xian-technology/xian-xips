# XSC002 Permit Authorizer

`XSC002` standardizes signature-based token approvals through a standalone
authorizer contract.

This is no longer a token extension that embeds `permit()` inside every token.
Instead, `XSC002` defines an external contract that verifies a signed approval
message and then calls a compatibility hook on the target token.

## Canonical Surface

```python
@export
def permit(
    token_contract: str,
    owner: str,
    spender: str,
    value: float,
    deadline: str,
    signature: str,
):
    ...
```

## Token Compatibility Requirements

To work with an XSC002 authorizer, a token should expose:

```python
@export
def approve_from_authorizer(owner: str, spender: str, amount: float):
    ...
```

That hook should:

- restrict callers to the configured permit authorizer
- write the allowance into the token's approvals state
- emit the token's normal `Approve` event

## Message Format

The signed message includes:

- `token_contract`
- `owner`
- `spender`
- `value`
- `deadline`
- `ctx.this`
- `chain_id`

The canonical message format is:

```python
f"{token_contract}:{owner}:{spender}:{value}:{deadline}:{ctx.this}:{chain_id}"
```

Including the token contract, authorizer contract, and chain id prevents replay
across contracts or networks.

## Expected Behavior

An XSC002 authorizer should:

- reject expired permits
- reject negative approval values
- reject reused permits
- verify the owner's signature
- call the target token's `approve_from_authorizer(...)`
- store the permit hash in `permits[permit_hash]`

## Event Model

The authorizer itself does not need a separate approval event. The compatible
token should emit its normal `Approve` event when the allowance is written.

## Notes

- `XSC002` complements `XSC001`; it does not replace it
- a token can be XSC001-compatible without supporting XSC002
- a token that supports XSC002 should still keep approval storage in its own
  token state
