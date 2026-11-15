# Real API compatibility fixtures

These are small, derived subsets of the pinned public GitHub REST and Stripe GA
OpenAPI descriptions, not full API descriptions or claims of complete support.
The manifest records original and derived digests, source and license URLs,
selected operations, and the extraction recipe. The adjacent license files
contain the complete upstream MIT notices. Retained operations, metadata and
reachable component values are preserved; unrelated paths, components, and
webhooks are omitted. No upstream fetch or provider request is needed for tests.

Doctor reports union-schema warnings for the Stripe operations. GitHub operation
IDs include upstream slashes. The plain-text GitHub zen response does not produce
an MCP output schema. Generated server builds use npm install, which may contact
the npm registry; they do not need provider credentials.

The Stripe fixture declares `created` and `types` as `deepObject`. Generated
stdio and streamable HTTP servers are exercised against a synthetic loopback
upstream for list queries and detail paths. These tests characterize the emitted
request targets, including repeated `types[]` keys, and decoded values; they do
not test Stripe server acceptance. The pinned official
[stripe-node 23.1.0 serializer](https://github.com/stripe/stripe-node/blob/6d5ed967d602224ac3056dc3f0befbb55487ee50/src/utils.ts)
uses indexed array keys such as `types[0]` and `types[1]`. Whether the endpoint
accepts the generated unindexed form is unresolved. The
[OpenAPI 3.0.0 parameter specification](https://spec.openapis.org/oas/v3.0.0.html#parameter-object)
does not define array serialization for `deepObject`.

Separately authored synthetic form cases live in `../form_compatibility/`; they
are not part of this pinned provider corpus.
