# Real API compatibility fixtures

These are small, derived subsets of the pinned public GitHub REST and Stripe GA
OpenAPI descriptions, not full API descriptions or claims of complete support.
The manifest records original and derived digests, source and license URLs,
selected operations, and the extraction recipe. The adjacent license files
contain the complete upstream MIT notices. Retained operations, metadata and
reachable component values are preserved; unrelated paths, components, and
webhooks are omitted. No upstream fetch or provider request is needed for tests.

Doctor reports union-schema warnings for the Stripe operations. GitHub operation
IDs include upstream slashes. Stripe's `created` object and `types` array use
`deepObject`; the suite checks their generated schema and metadata, not wire
serialization. In particular, the generated deepObject branch only handles
objects that are not arrays. The plain-text GitHub zen response does not produce
an MCP output schema. Generated server builds use npm install, which may contact
the npm registry; they do not need provider credentials.

Separately authored synthetic form cases live in `../form_compatibility/`; they
are not part of this pinned provider corpus.
