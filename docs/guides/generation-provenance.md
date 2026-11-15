# Generation provenance

Pass `--provenance` to `generate` or `run` to add a versioned `provenance` object to `generation_report.json`. It is off by default and cannot be enabled by policy defaults. **Unsalted hashes are not redaction:** someone can test guesses about a spec or policy projection against them. Treat the report as sensitive and inspect the whole report before sharing; existing fields such as `policy_file`, logs, and generated files have their own contents.

Version 1 records the installed `openapi-to-mcp-cli` distribution version (or null when unavailable), source kind (`file` or `url`), and a SHA-256 of the already-loaded top-level decoded text encoded as UTF-8. The text is the text passed to YAML parsing, not a canonical semantic representation or necessarily the original bytes. File reading may normalize line endings; HTTP decoding follows the response encoding. Formatting and Unicode differences matter. Local `#/` references are covered only as part of that text. External reference contents are not included; the validator may independently read external resources.

`resolved_options` contains grouping, tool description and name policies, telemetry, transport kind, strictness, runtime validation, and effective mapping and schema error modes. `config_projection_digest` hashes exactly those values. Identity overrides or spec-derived identity, host, port, endpoint, and runtime overrides are omitted.

`policy_projection` reports only whether a policy and each section is present. `policy_digest` hashes a private projection of sorted include/exclude selectors, rename maps, annotation booleans and execution integers, including their operation/name associations. It excludes auth and description values, generation defaults, source paths and unknown fields. Section presence for auth and descriptions is still reported. Missing and empty policies differ, but excluded changes can produce identical digests. The report never contains the private projection itself. Selector and rename guesses can nevertheless be checked against the hash.

Both projection hashes use compact JSON with sorted keys, unescaped Unicode, no Unicode normalization and no non-finite numbers, encoded as UTF-8 and hashed with SHA-256. The record has no timestamp, source URL, local source path, environment values, raw source content or custom-file hash. It does not cover existing custom files, the output tree, templates, dependency resolution or the runtime environment. The version identifies installed distribution metadata, not a source revision. Equal provenance does not guarantee identical output or reproducibility.

A version 1 record has this shape (digest values abbreviated here):

```json
{
  "schema_version": 1,
  "generator": {"distribution": "openapi-to-mcp-cli", "version": "0.13.0"},
  "spec": {"source_kind": "file", "digest": {"algorithm": "sha256", "scope": "loaded-top-level-text-utf8", "value": "..."}},
  "resolved_options": {"tool_grouping": "none", "tool_descriptions": "spec", "tool_name_policy": "preserve", "telemetry": "off", "transport": "stdio", "strict": true, "runtime_validation": "input", "on_mapping_error": "fail", "on_schema_error": "fail"},
  "config_projection_digest": {"algorithm": "sha256", "scope": "resolved-options-v1", "value": "..."},
  "policy_projection": {"present": false, "include": false, "exclude": false, "rename": false, "auth": false, "annotations": false, "execution": false, "descriptions": false},
  "policy_digest": {"algorithm": "sha256", "scope": "non-auth-policy-projection-v1", "value": "...", "captured": ["include", "exclude", "rename", "annotations", "execution"], "excluded": ["auth", "descriptions", "generation_defaults", "source_path", "unknown_fields"]}
}
```

Actual digest values contain 64 lowercase hexadecimal characters. The version and options shown are examples.
