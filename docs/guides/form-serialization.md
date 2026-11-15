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
other styles, and `allowReserved: true` are unsupported.

A whole query cannot coexist with ordinary query parameters, an existing base
URL query or fragment, or a colliding input name. Query credentials may be
appended to a form only when no emitted field name collides. Whole JSON and
text queries cannot be combined with query credentials. Whole-query audit data
is redacted as a constant marker. Request-body audit redaction continues to use
the logical body paths.

## Migration

Earlier generated servers relied on Axios's implicit form serializer. It could
emit names such as `tags[]` and `object[key]`. Form serialization now follows
the selected schema and encoding instead: arrays generally repeat the field
name, and objects default to JSON. Verify affected endpoints and their wire
expectations before replacing generated servers. Ordinary query parameters and
JSON/text request bodies retain their previous behavior.
