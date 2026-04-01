# Xian Standards and Improvement Proposals

`xian-xips` is the umbrella repository for standards and proposal documents in
the Xian ecosystem.

Today the repo mainly contains contract standards, but it is intentionally not
limited to contracts. As the protocol and tooling surface grows, the same repo
can also host standards for areas such as:

- protocol behavior
- governance processes
- RPC and API conventions
- wallet signing formats
- indexer and event schemas
- tooling and interoperability requirements

## Standards Families

The current family in this repository is:

- `XSC###`: Xian Standard Contract

Additional families can be introduced as needed without changing the role of
the repository itself.

## Current Standards

- `XSC001`: standard fungible token core
- `XSC002`: permit authorizer for signature-based approvals
- `XSC003`: streaming token
- `XSC004`: wrapped token

## Repository Conventions

- Each standard lives in its own directory.
- The directory contains a human-readable `README.md`.
- Reference implementations live alongside the README.
- Tests should describe the intended interoperability behavior of the
  standard, not just one implementation detail.

## Scope Guidance

Use this repo when a proposal needs a stable, shared convention across the
Xian universe. That can include contract interfaces, contract behavior, signed
message formats, event schemas, governance procedures, or other interoperability
surfaces.

If a proposal is specific to one app or one private deployment, it generally
does not belong here.

## Testing

Most contract standards in this repository include Contracting-based reference
tests. Use the local Xian contract development environment that matches the
rest of the stack when running them.
