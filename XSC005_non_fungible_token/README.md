# XSC005 Non-Fungible Token Contract

The **XSC005** standard defines the core non-fungible token interface for
Xian. It gives wallets, explorers, marketplaces, and indexers a shared
ownership, approval, metadata, and event surface for NFT collections.

XSC005 is intentionally a single-contract standard by default. Collections can
store arbitrary media on-chain through MIME type, encoding, inline content,
content hashes, and optional chunks. Collection-specific rendering formats,
marketplace helpers, royalties, likes, and ownership proofs are additive
extensions rather than minimum compliance requirements.

## Required State

An XSC005 collection exposes these storage hashes:

```python
owners = Hash(default_value="")
balances = Hash(default_value=0)
approvals = Hash(default_value="")
operator_approvals = Hash(default_value=False)
metadata = Hash()
token_data = Hash(default_value="")
```

The collection-level `metadata` hash must include:

- `standard`: exactly `XSC-0005`
- `collection_name`
- `collection_symbol`
- `collection_description`

## Required Functions

```python
@export
def change_metadata(key: str, value: Any):
    ...

@export
def balance_of(owner: str) -> int:
    ...

@export
def owner_of(token_id: str) -> str:
    ...

@export
def exists(token_id: str) -> bool:
    ...

@export
def transfer(token_id: str, to: str):
    ...

@export
def approve(token_id: str, to: str):
    ...

@export
def revoke(token_id: str):
    ...

@export
def get_approved(token_id: str) -> str:
    ...

@export
def set_approval_for_all(operator: str, approved: bool):
    ...

@export
def is_approved_for_all(owner: str, operator: str) -> bool:
    ...

@export
def transfer_from(token_id: str, to: str, main_account: str):
    ...

@export
def token_metadata(token_id: str) -> dict:
    ...

@export
def contract_metadata() -> dict:
    ...
```

## Expected Semantics

- each `token_id` has at most one owner
- `balance_of(owner)` returns the number of live tokens owned by `owner`
- `transfer` moves a token owned by `ctx.caller`
- `approve` grants one spender authority over one token
- `set_approval_for_all` grants an operator authority over all caller-owned
  tokens
- `transfer_from` may be called by the owner, token-approved spender, or an
  approved operator
- successful transfers clear the single-token approval
- `token_metadata` returns owner and render or verification metadata for the
  asset

## Recommended Token Metadata

```python
token_data[token_id, "name"] = "Example"
token_data[token_id, "description"] = "On-chain asset"
token_data[token_id, "creator"] = ctx.caller
token_data[token_id, "created"] = now
token_data[token_id, "mime_type"] = "image/svg+xml"
token_data[token_id, "encoding"] = "utf8"
token_data[token_id, "content"] = "<svg>...</svg>"
token_data[token_id, "content_hash"] = hashlib.sha256(content)
token_data[token_id, "uri"] = ""
```

For larger assets, collections may store chunks:

```python
content_chunks[token_id, index] = chunk
token_data[token_id, "chunk_count"] = count
token_data[token_id, "content_hash"] = full_payload_hash
```

## Optional PixelGrid Extension

Pixel-art collections can expose custom palettes and compact frame data without
making palette rendering part of the required XSC005 surface. The reference
contract uses this storage shape:

```python
palettes[palette_id, "size"] = 4
palettes[palette_id, "locked"] = True
palettes[palette_id, index] = "#ff00aa"

token_data[token_id, "render_schema"] = "xian.pixelgrid.v1"
token_data[token_id, "palette_id"] = palette_id
token_data[token_id, "width"] = 25
token_data[token_id, "height"] = 25
token_data[token_id, "frame_count"] = 8
token_data[token_id, "frame_delay_ms"] = 120
token_data[token_id, "pixel_encoding"] = "palette-index-64"
token_data[token_id, "content"] = "0123..."
```

`palette-index-64` uses this alphabet:

```text
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-
```

Each character is one pixel whose index must be lower than the locked palette
size. Lock palettes before minting so token art does not change after
issuance.

For PixelGrid assets, hash a domain-separated render source:

```python
hash_source = (
    "xian.pixelgrid.v1"
    + ":"
    + palette_id
    + ":"
    + str(width)
    + ":"
    + str(height)
    + ":"
    + str(frame_count)
    + ":"
    + str(frame_delay_ms)
    + ":"
    + pixels
)
token_data[token_id, "content_hash"] = hashlib.sha256(hash_source)
```

## Expected Events

Core XSC005 collections should emit:

- `Transfer`
- `Approval`
- `ApprovalForAll`
- `MetadataUpdate`

Marketplace, royalty, PixelGrid, likes, and proof events are extensions.

## Files

- `XSC0005.py`: on-chain interface checker
- `XSC0005_nft.py`: reference NFT collection implementation
- `tests/test.py`: interoperability tests for the checker and reference
  implementation

## Compatibility Notes

- keep function names and argument names stable so
  `importlib.enforce_interface` can validate collections
- prefer one contract for ordinary NFT collections
- split metadata or rendering into a companion contract only when there is a
  strong reason, and guard every mutating companion function with a controller
  check
- keep collection-specific rendering formats additive to the core NFT standard
- keep return payloads under the chain return-size limit
