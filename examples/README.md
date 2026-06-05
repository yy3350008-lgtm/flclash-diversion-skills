# Examples

This directory contains generic example configs for testing and demonstration.

## Files

- `generic-main.yaml` — A minimal base config with three proxies (Proxy-A/B/C),
  a `Main` select group, and basic rules. Proxies use `type: direct` stubs with
  no server, port, or credentials.
- `generic-secondary.yaml` — A secondary config with three proxies
  (Secondary-Alpha/Beta/Gamma) and no groups or rules. Proxies use `type: direct`
  stubs. The merge script creates groups automatically.

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

All proxy entries in these example files use `type: direct` stubs with **no
server, port, uuid, password, or token fields**. They are structural examples
only — not usable proxy configurations.

**Never commit real credentials.** Use `.gitignore` patterns like `*.local.yaml`
and `*.secret.yaml` for your actual configs.
