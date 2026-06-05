# Examples

This directory contains generic example configs for testing and demonstration.

## Files

- `generic-main.yaml` — A minimal base config with three proxies (Proxy-A/B/C),
  a `Main` select group, and basic rules. Uses placeholder IPs from RFC 5737
  documentation ranges and dummy UUIDs.
- `generic-secondary.yaml` — A secondary config with three proxies
  (Secondary-Alpha/Beta/Gamma) and no groups or rules. The merge script creates
  groups automatically.

## Usage

```bash
python scripts/merge_flclash_configs.py \
  --base examples/generic-main.yaml \
  --secondary examples/generic-secondary.yaml \
  --output output.yaml \
  --main-group Main \
  --secondary-group Secondary-Main \
  --target-group NotebookLM \
  --target-domain notebooklm.google \
  --target-node Secondary-Alpha
```

## Privacy

All IPs, UUIDs, and passwords in these files are placeholders:

- IPs use RFC 5737 documentation ranges (`203.0.113.x`, `198.51.100.x`, `192.0.2.x`)
- UUIDs are all-zeros with a trailing digit
- Passwords are `changeme`

**Never commit real credentials.** Use `.gitignore` patterns like `*.local.yaml`
and `*.secret.yaml` for your actual configs.
