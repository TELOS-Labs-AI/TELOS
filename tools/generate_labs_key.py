#!/usr/bin/env python3
"""Generate TELOS Labs Ed25519 key pair for activation counter-signing.

ONE-TIME USE. Run this once to generate the Labs root key pair.

Output:
  - Private key hex (store as Supabase secret: TELOS_LABS_PRIVATE_KEY)
  - Public key hex (embed in pa_signing.py as TELOS_LABS_PUBLIC_KEY)
  - PEM files saved to ~/.telos/labs/ (backup only)

Usage:
    python3 scripts/generate_labs_key.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telos_governance.signing import SigningKeyPair


def main():
    # Generate the Labs key pair
    kp = SigningKeyPair.generate()

    private_hex = kp.private_key_bytes.hex()
    public_hex = kp.public_key_bytes.hex()
    fingerprint = kp.fingerprint

    # Save PEM backups
    labs_dir = Path.home() / ".telos" / "labs"
    labs_dir.mkdir(parents=True, exist_ok=True)

    private_pem = labs_dir / "telos_labs.key"
    public_pem = labs_dir / "telos_labs.pub"

    if private_pem.exists():
        print(f"ERROR: Labs key already exists at {private_pem}")
        print("       Delete it first if you want to regenerate (this is destructive).")
        sys.exit(1)

    kp.save_private_pem(private_pem)
    kp.save_public_pem(public_pem)

    print("=" * 60)
    print("  TELOS Labs Root Key Pair Generated")
    print("=" * 60)
    print()
    print("  1. SUPABASE SECRET (store with `supabase secrets set`):")
    print()
    print(f"     TELOS_LABS_PRIVATE_KEY={private_hex}")
    print()
    print("  2. PUBLIC KEY CONSTANT (embed in pa_signing.py):")
    print()
    print(f'     TELOS_LABS_PUBLIC_KEY = "{public_hex}"')
    print()
    print(f"  3. Fingerprint: {fingerprint}")
    print()
    print(f"  4. PEM backups saved to:")
    print(f"     Private: {private_pem}")
    print(f"     Public:  {public_pem}")
    print()
    print("  IMPORTANT:")
    print("  - The private key hex above is the ONLY thing that goes")
    print("    into Supabase secrets. Guard it carefully.")
    print("  - The public key hex gets embedded in the CLI source code")
    print("    so customers can verify counter-signatures offline.")
    print("  - If you lose the private key, all existing counter-signatures")
    print("    remain valid but you cannot issue new ones.")
    print("=" * 60)


if __name__ == "__main__":
    main()
