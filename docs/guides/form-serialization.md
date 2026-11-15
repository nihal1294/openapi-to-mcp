# Form and whole-query serialization

OpenAPI 3.2 `in: querystring` parameters expose their declared name as a tool
argument. Supported whole-query content types are `application/json`,
`text/plain` (string), and `application/x-www-form-urlencoded` (object).
The name is an input label and is not added to the query. JSON and text are
percent-encoded once; an empty query need not retain a trailing `?`.

Form request bodies and whole-query forms accept declared primitive fields,
primitive arrays, and JSON-valued objects. A supported `additionalProperties`
schema can describe other fields; otherwise unknown fields fail. Null and
undefined fields and empty arrays are omitted; empty strings emit `name=`.
An optional top-level null is omitted, and a required top-level null is missing.
These null rules are generator behavior, not a universal server convention.

Without explicit `style`, `explode`, or `allowReserved`, field content uses
form encoding, including `+` for spaces. Objects default to JSON. Explicit
`application/json` content serializes a field as JSON. When any style flag is
present, form style takes precedence and uses component escaping; flat objects
can expand into separate names or use comma-separated tokens. OpenAPI 3.0 and
3.1 form-style arrays with `explode: false` use comma-separated items. OpenAPI
3.2 applies the encoding to each array item and repeats the field name.
Nested styled values, nested Encoding Objects, binary fields, multipart bodies,
other styles, and `allowReserved: true` are unsupported. A top-level form can
use a nonempty `allOf` of explicitly typed object branches with disjoint,
explicitly typed primitive scalar properties and branch-local required lists.
Pure local references are supported. This subset allows scalar enum, const,
string length and pattern, and numeric minimum, maximum and multipleOf
constraints, plus ordinary field annotations. Object closure, additional
assertions, nested composition, and reference siblings are unsupported in this
layout. The original composition remains in the validation schema. Unknown
fields are still rejected by form serialization even when the original schema
permits them. Other composed form layouts and composed styled objects are
unsupported. JSON-valued object fields can contain composed
schemas because they are serialized as a single JSON value. For form schema
references, siblings that change the serialized type or array items are
unsupported. When an object must be expanded, reference siblings that declare
properties, required fields, additional properties, or pattern properties are
also unsupported. Pattern properties, conditional schemas and schema-valued
dependencies are unsupported in expanded objects. Validation-only constraints,
including property names and property-list dependencies, remain supported.
Binary metadata is unsupported even when it appears beside a reference. Ordinary schema constraints and JSON-valued object contents can
still use supported references.

A whole query cannot coexist with ordinary query parameters, an existing base
URL query or fragment, or a colliding input name. Query credentials may be
appended to a form only when no emitted field name collides. Whole JSON and
text queries cannot be combined with query credentials. Whole-query audit data
is redacted as a constant marker. Request-body audit redaction continues to use
the logical body paths.

## Migration

Earlier generated servers relied on Axios's implicit form serializer, which
could emit bracketed field names such as `tags[]` and `object[key]`. Declared
form encoding now determines the wire shape. In content mode with default
content types, primitive arrays use `tags=a&tags=b`; with explicit
`application/json` content, each array item is JSON-serialized before form
encoding. Content-mode objects use JSON such as
`object=%7B%22key%22%3A%22value%22%7D`. Explicit object styles may expand fields
or use comma-separated tokens. With `style: form, explode: false`, OpenAPI
3.0/3.1 arrays emit `tags=a,b`; OpenAPI 3.2 applies these settings per item
and emits `tags=a&tags=b`. Verify each affected endpoint's wire
expectations before replacing generated servers. Ordinary query parameters and
JSON/text request bodies retain their previous behavior.
