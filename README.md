# bulk_credential_import

Bulk-creates Forward Networks EXPERT_MODE CLI credentials from a CSV/JSON file
and associates each one with its device.

## Usage

```
pip install -r requirements.txt
python bulk_credential_import.py --network-id <network-id> --api-key <api-key> <input_file.csv|input_file.json>
```

You will be prompted for the API secret (used with the API key for HTTP basic auth).

`--url` defaults to `https://fwd.app` and can be overridden for on-prem/other instances.

## Input format

A CSV (see [example_devices.csv](example_devices.csv)) or JSON file with a
`device_name` and `expert_mode_password` per row/object, e.g.:

```csv
device_name,expert_mode_password
router-01,correct-horse-battery-staple
switch-02,another-s3cr3t-p4s$w0rd
```

## What it does

1. Loads the input file.
2. Creates one EXPERT_MODE CLI credential per row in a single bulk `PATCH
   .../cli-credentials` call, named `Expert_mode_<device_name>`.
3. Associates each created credential with its device via a `PATCH
   .../classic-devices/<device_name>` call (one call per device).
4. Writes the results to `<input_file>_with_credentials.<ext>`, alongside the
   original columns, with two added columns: `credential_id` and
   `association_status` (`success` or `failure` per device).

Credential-creation failures abort the run; individual device-association
failures are logged and skipped so the rest of the batch still completes.
