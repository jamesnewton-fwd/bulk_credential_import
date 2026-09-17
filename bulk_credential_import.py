#!/usr/bin/env python3
"""Bulk-import credentials into Forward Networks and associate them with devices."""

import argparse
import csv
import getpass
import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bulk-create Forward Networks credentials from a CSV/JSON file "
        "and associate them with devices."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to a .csv or .json file describing the credentials to import.",
    )
    parser.add_argument(
        "--url",
        default="https://fwd.app",
        help="Forward Networks base URL (default: %(default)s).",
    )
    parser.add_argument(
        "--network-id",
        required=True,
        help="Forward Networks network ID.",
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="Forward Networks API key (used as the basic auth username).",
    )
    return parser.parse_args()


def load_records(input_file: Path):
    """Load credential/device records from a CSV or JSON file.

    Returns a list of dicts, one per record. The exact schema (field names,
    how credentials map to devices, etc.) is TBD.
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    suffix = input_file.suffix.lower()
    if suffix == ".csv":
        with input_file.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    elif suffix == ".json":
        with input_file.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = [data]
        return data
    else:
        raise ValueError(f"Unsupported input file type: {suffix} (expected .csv or .json)")


def create_credentials(session: requests.Session, base_url: str, network_id: str, records):
    """Bulk-create EXPERT_MODE CLI credentials, one per record.

    Sends a single PATCH request with all records, since the API creates
    credentials in bulk and returns them in the same order as the request.
    Adds a "credential_id" key to each record in place and returns records.
    """
    url = f"{base_url}/api/networks/{network_id}/cli-credentials"
    payload = [
        {
            "type": "EXPERT_MODE",
            "name": f"Expert_mode_{record['device_name']}",
            "password": record["expert_mode_password"],
            "autoAssociate": False,
        }
        for record in records
    ]

    response = session.patch(url, json=payload)
    response.raise_for_status()
    created = response.json()

    if len(created) != len(records):
        raise RuntimeError(
            f"Expected {len(records)} created credentials back, got {len(created)}"
        )

    for record, credential in zip(records, created):
        record["credential_id"] = credential["id"]

    return records


def associate_credentials(session: requests.Session, base_url: str, network_id: str, records):
    """Associate each record's credential with its device, one PATCH call per device.

    Failures on individual devices are reported but don't stop the rest of the batch.
    """
    ok = 0
    for record in records:
        device_name = record["device_name"]
        url = (
            f"{base_url}/api/networks/{network_id}/classic-devices/"
            f"{quote(device_name, safe='')}"
        )
        payload = {"cliCredential3Id": record["credential_id"]}

        response = session.patch(url, json=payload)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            print(
                f"Error associating credential with device {device_name!r}: {exc}\n{response.text}",
                file=sys.stderr,
            )
            record["association_status"] = "failure"
            continue
        record["association_status"] = "success"
        ok += 1

    print(f"Associated credentials with {ok}/{len(records)} devices")
    return records


def write_records(output_file: Path, records):
    """Write records (with credential_id filled in) back out as CSV or JSON."""
    if not records:
        return

    suffix = output_file.suffix.lower()
    if suffix == ".csv":
        fieldnames = list(records[0].keys())
        with output_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
    else:
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)


def main():
    args = parse_args()

    api_secret = getpass.getpass("API secret: ")

    try:
        records = load_records(args.input_file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    session = requests.Session()
    session.auth = HTTPBasicAuth(args.api_key, api_secret)

    try:
        records = create_credentials(session, args.url, args.network_id, records)
    except requests.HTTPError as exc:
        print(f"Error creating credentials: {exc}\n{exc.response.text}", file=sys.stderr)
        sys.exit(1)

    print(f"Created {len(records)} credentials.")

    records = associate_credentials(session, args.url, args.network_id, records)

    output_file = args.input_file.with_name(
        f"{args.input_file.stem}_with_credentials{args.input_file.suffix}"
    )
    write_records(output_file, records)
    print(f"Wrote results to {output_file}")


if __name__ == "__main__":
    main()
