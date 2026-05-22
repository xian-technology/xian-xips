# XSC002 Permit Authorizer

`XSC002` standardizes signature-based token approvals through a standalone
authorizer contract.

`XSC002` defines an external contract that verifies a signed approval message
and then calls a compatibility hook on the target token.

## Canonical Surface

```python
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
    ...
```

The authorizer stores `nonces[owner]` and only accepts the owner's current
nonce. A successful permit increments that nonce.

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

The signed message is newline-separated and versioned:

```text
xian-permit-v2
chain_id:{chain_id}
authorizer:{authorizer_contract}
token_contract:{token_contract}
owner:{owner}
spender:{spender}
amount:{canonical_amount}
deadline:{deadline}
nonce:{nonce}
```

`canonical_amount` is the decimal value after contract-side normalization with
`decimal(str(value))`. Including the token contract, authorizer contract, chain
id, and nonce prevents replay across contracts, networks, and permit slots.

## Expected Behavior

An XSC002 authorizer should:

- reject expired permits
- reject negative approval values
- reject non-current nonces
- verify the owner's signature
- increment `nonces[owner]` after a successful verification
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
