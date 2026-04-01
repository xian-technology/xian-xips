# XSC003 Streaming Token

`XSC003` extends the XSC001 fungible-token model with native streaming payment
primitives.

This standard is for a standalone streaming token contract. It keeps the normal
token surface and adds stream lifecycle methods. Signature-based permit logic is
not part of XSC003; if a deployment also wants that behavior, combine the token
with an external XSC002 permit authorizer.

## XSC001 Core

An XSC003 token is expected to preserve the XSC001 surface:

- `change_metadata`
- `transfer`
- `approve`
- `transfer_from`
- `balance_of`

It should keep balances and approvals in separate hashes.

## Streaming Surface

```python
@export
def create_stream(receiver: str, rate: float, begins: str, closes: str):
    ...

@export
def balance_stream(stream_id: str):
    ...

@export
def change_close_time(stream_id: str, new_close_time: str):
    ...

@export
def finalize_stream(stream_id: str):
    ...

@export
def close_balance_finalize(stream_id: str):
    ...

@export
def balance_finalize(stream_id: str):
    ...

@export
def forfeit_stream(stream_id: str):
    ...
```

## Stream Model

The canonical stream state tracks:

- `sender`
- `receiver`
- `begins`
- `closes`
- `rate`
- `claimed`
- `status`

Streams use a deterministic `stream_id`.

Accrual is lazy. Nothing runs between blocks. The amount due is calculated when
`balance_stream` or one of the convenience helpers is executed in a later block.

## Event Expectations

Implementations should emit:

- `Transfer`
- `Approve`
- `StreamCreated`
- `StreamBalance`
- `StreamCloseChange`
- `StreamForfeit`
- `StreamFinalized`

## Notes

- XSC003 does not standardize `create_stream_from_permit`
- XSC003 does not require a `permits` hash
- If signature-based approvals are needed, pair the token with XSC002 instead
  of embedding permit logic into the streaming token itself
