# XSC001 Standard Token

`XSC001` defines the core fungible-token surface for Xian.

This standard is intentionally narrow. It covers balances, approvals, metadata,
and delegated transfers. It does not include permit signing or streaming
payments. Those belong to separate standards.

## Required Surface

```python
@export
def change_metadata(key: str, value: Any):
    ...

@export
def transfer(amount: float, to: str):
    ...

@export
def approve(amount: float, to: str):
    ...

@export
def transfer_from(amount: float, to: str, main_account: str):
    ...

@export
def balance_of(address: str):
    ...
```

## State Layout

The standard token keeps balances and approvals separate:

```python
balances = Hash(default_value=0)
approvals = Hash(default_value=0)
metadata = Hash()
operator = Variable()
```

- `balances[address]` stores spendable token balances
- `approvals[owner, spender]` stores delegated spending allowances
- `operator.get()` controls who may update token metadata in the canonical
  implementation

## Expected Semantics

- `transfer` moves tokens from `ctx.caller` to `to`
- `approve` overwrites the allowance for `to`
- `approve` may set the allowance to `0`
- `transfer_from` spends from `main_account` using
  `approvals[main_account, ctx.caller]`
- `balance_of` returns the balance for an address

## Recommended Metadata Keys

Common metadata fields for XSC001 implementations are:

- `token_name`
- `token_symbol`
- `token_logo_url`
- `token_website`
- `total_supply`

## Events

Implementations should emit:

- `Transfer`
- `Approve`

Sender and recipient or spender should be indexed so explorers and subscribers
can query them efficiently.

## Compatibility Notes

- Use non-negative approvals and overwrite semantics
- Keep argument names stable for SDK and tooling interoperability
- If a token also wants to support XSC002, it can add an
  `approve_from_authorizer(owner, spender, amount)` extension without changing
  the XSC001 core surface
