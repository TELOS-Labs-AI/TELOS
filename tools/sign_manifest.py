#!/usr/bin/env python3
"""
Sign a TELOS version manifest with the Labs private key.

Reads manifest.json, signs with Ed25519, writes manifest.json.sig (64 bytes).
This is a TELOS Labs internal tool — not shipped to customers.

Usage:
    python scripts/sign_manifest.py manifest.json --key labs.pem

Output:
    manifest.json.sig  (64-byte Ed25519 signature)
"""

import argparse
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telos_governance.signing import SigningKeyPair, SigningError


def main():
    parser = argparse.ArgumentParser(
        description="Sign a TELOS version manifest with Ed25519."
    )
    parser.add_argument(
        "manifest", type=Path, help="Path to manifest.json"
    )
    parser.add_argument(
        "--key", required=True, type=Path,
        help="Path to Labs private key PEM file."
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output path for signature (default: <manifest>.sig)."
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"Error: {args.manifest} not found", file=sys.stderr)
        sys.exit(1)

    if not args.key.exists():
        print(f"Error: {args.key} not found", file=sys.stderr)
        sys.exit(1)

    try:
        kp = SigningKeyPair.from_private_pem(args.key)
    except SigningError as e:
        print(f"Error loading key: {e}", file=sys.stderr)
        sys.exit(1)

    manifest_bytes = args.manifest.read_bytes()
    signature = kp.sign(manifest_bytes)

    output_path = args.output or Path(str(args.manifest) + ".sig")
    output_path.write_bytes(signature)

    print(f"Signed {args.manifest} ({len(manifest_bytes)} bytes)")
    print(f"Signature: {output_path} ({len(signature)} bytes)")
    print(f"Public key fingerprint: {kp.fingerprint}")


if __name__ == "__main__":
    main()
