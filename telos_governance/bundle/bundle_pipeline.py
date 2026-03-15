"""
Bundle Provisioning Pipeline: One-command customer delivery.

This is the TELOS Labs build-side orchestrator. It takes a YAML config
and produces a complete customer delivery package -- everything needed
to activate and run a governed AI agent.

Delivery directory structure:
    delivery/
    ├── {agent_id}.telos            # Encrypted, dual-signed governance bundle
    ├── {agent_id}.telos-license    # Ed25519-signed license token
    ├── license.key                 # 32-byte symmetric key (deliver separately)
    ├── deploy.pub                  # Deployment public key (32 bytes)
    ├── labs.pub                    # Labs public key (32 bytes, for verification)
    └── DELIVERY_MANIFEST.json      # Cleartext metadata for the delivery

Security model:
    - license.key MUST be delivered out-of-band (USB, secure channel)
    - The .telos bundle and .telos-license can be delivered over any channel
    - deploy.pub and labs.pub are public -- safe to distribute openly
    - DELIVERY_MANIFEST.json is cleartext metadata, no secrets

Usage:
    from telos_governance.bundle_pipeline import BundleProvisioner

    provisioner = BundleProvisioner(labs_key=labs_kp)
    result = provisioner.provision(
        config_path="agent.yaml",
        agent_id="property-intel-v2",
        output_dir="./delivery/acme",
        licensee_id="jane.doe@acme.com",
        licensee_org="Acme Insurance Corp",
        risk_classification="high_risk",
        expires_in_days=365,
    )

CLI:
    telos bundle provision agent.yaml \\
        --labs-key labs.pem \\
        --agent-id property-intel-v2 \\
        --output-dir ./delivery/acme \\
        --licensee-org "Acme Insurance" \\
        --risk-classification high_risk \\
        --expires-in-days 365

NIST AI RMF: This module implements MAP 2.2 (upstream dependency documentation)
and Govern (policy enforcement through signed, versioned configuration artifacts).
The delivery manifest serves as the system characterization record per NIST AI 600-1.
"""

import json
import os
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from telos_governance.signing import SigningKeyPair, SigningError
from telos_governance.bundle import BundleBuilder, BundleError
from telos_governance.licensing import LicenseTokenBuilder, LicenseError


class ProvisioningError(Exception):
    """Raised when bundle provisioning fails."""
    pass


@dataclass
class ProvisioningResult:
    """Result of a bundle provisioning operation.

    Contains paths to all generated artifacts and metadata
    about the provisioned delivery.
    """
    bundle_path: str = ""
    token_path: str = ""
    license_key_path: str = ""
    deploy_pub_path: str = ""
    labs_pub_path: str = ""
    manifest_path: str = ""
    # Metadata
    agent_id: str = ""
    bundle_id: str = ""
    deployment_fingerprint: str = ""
    labs_fingerprint: str = ""
    licensee_id: str = ""
    licensee_org: str = ""
    risk_classification: str = ""
    expires_in_days: Optional[int] = None


class BundleProvisioner:
    """Orchestrates complete customer delivery provisioning.

    This is TELOS Labs internal tooling. Customers never use this directly.
    It combines BundleBuilder + LicenseTokenBuilder into a single
    provisioning workflow that produces all delivery artifacts.

    Args:
        labs_key: TELOS Labs Ed25519 signing key pair.
    """

    def __init__(self, labs_key: SigningKeyPair):
        self._labs_key = labs_key

    def provision(
        self,
        config_path: str,
        output_dir: str,
        agent_id: str = "",
        description: str = "",
        telos_version: str = "",
        licensee_id: str = "",
        licensee_org: str = "",
        risk_classification: str = "",
        regulatory_jurisdiction: str = "",
        expires_in_days: Optional[int] = None,
        capabilities: Optional[list] = None,
        boundary_ids: str = "",
    ) -> ProvisioningResult:
        """Provision a complete customer delivery.

        Generates deployment keys, license key, builds the bundle,
        builds the license token, and writes all artifacts to output_dir.

        Args:
            config_path: Path to YAML configuration file.
            output_dir: Directory for delivery artifacts.
            agent_id: Agent identifier (used in bundle manifest and token).
            description: Human-readable bundle description.
            telos_version: TELOS version string.
            licensee_id: Individual licensee identifier.
            licensee_org: Organization holding the license.
            risk_classification: Risk level (high_risk, limited_risk, etc.).
            regulatory_jurisdiction: Comma-separated jurisdiction identifiers.
            expires_in_days: Days until license expiration (None = perpetual).
            capabilities: List of authorized capabilities.
            boundary_ids: Comma-separated boundary identifiers.

        Returns:
            ProvisioningResult with paths to all generated artifacts.

        Raises:
            ProvisioningError: If provisioning fails at any step.
        """
        try:
            # Load config data
            config_data = self._load_config(config_path)

            # Generate deployment key pair for this customer
            deploy_key = SigningKeyPair.generate()

            # Generate random 32-byte license key
            license_key = secrets.token_bytes(32)

            # Build the .telos bundle
            builder = BundleBuilder(
                labs_key=self._labs_key,
                deployment_key=deploy_key,
            )
            bundle_bytes = builder.build(
                config_data=config_data,
                license_key=license_key,
                agent_id=agent_id,
                description=description,
                telos_version=telos_version,
                risk_classification=risk_classification,
                regulatory_jurisdiction=regulatory_jurisdiction,
                boundary_ids=boundary_ids,
            )

            # Extract bundle_id from the built bundle (it was auto-generated)
            from telos_governance.bundle import BundleReader
            reader = BundleReader(bundle_bytes)
            bundle_id = reader.manifest.bundle_id

            # Build the .telos-license token
            token_builder = LicenseTokenBuilder(labs_key=self._labs_key)
            token_bytes = token_builder.build(
                agent_id=agent_id,
                deployment_fingerprint=deploy_key.fingerprint,
                license_key=license_key,
                capabilities=capabilities,
                expires_in_days=expires_in_days,
                bundle_id=bundle_id,
                licensee_id=licensee_id,
                licensee_org=licensee_org,
                risk_classification=risk_classification,
            )

            # Write all artifacts
            result = self._write_artifacts(
                output_dir=output_dir,
                agent_id=agent_id,
                bundle_bytes=bundle_bytes,
                token_bytes=token_bytes,
                license_key=license_key,
                deploy_key=deploy_key,
                bundle_id=bundle_id,
                licensee_id=licensee_id,
                licensee_org=licensee_org,
                risk_classification=risk_classification,
                expires_in_days=expires_in_days,
            )

            return result

        except (BundleError, LicenseError, SigningError) as e:
            raise ProvisioningError(f"Provisioning failed: {e}") from e
        except ProvisioningError:
            raise
        except Exception as e:
            raise ProvisioningError(f"Unexpected provisioning error: {e}") from e

    def _load_config(self, config_path: str) -> bytes:
        """Load configuration file as bytes."""
        path = Path(config_path)
        if not path.exists():
            raise ProvisioningError(f"Config file not found: {config_path}")
        try:
            return path.read_bytes()
        except Exception as e:
            raise ProvisioningError(f"Failed to read config: {e}") from e

    def _write_artifacts(
        self,
        output_dir: str,
        agent_id: str,
        bundle_bytes: bytes,
        token_bytes: bytes,
        license_key: bytes,
        deploy_key: SigningKeyPair,
        bundle_id: str,
        licensee_id: str,
        licensee_org: str,
        risk_classification: str,
        expires_in_days: Optional[int],
    ) -> ProvisioningResult:
        """Write all delivery artifacts to the output directory."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # File names
        safe_id = agent_id or "agent"
        bundle_file = out / f"{safe_id}.telos"
        token_file = out / f"{safe_id}.telos-license"
        license_key_file = out / "license.key"
        deploy_pub_file = out / "deploy.pub"
        labs_pub_file = out / "labs.pub"
        manifest_file = out / "DELIVERY_MANIFEST.json"

        # Write bundle
        bundle_file.write_bytes(bundle_bytes)

        # Write license token
        token_file.write_bytes(token_bytes)

        # Write license key (restricted permissions -- sensitive)
        fd = os.open(str(license_key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, license_key)
        finally:
            os.close(fd)

        # Write public keys (not sensitive)
        deploy_pub_file.write_bytes(deploy_key.public_key_bytes)
        labs_pub_file.write_bytes(self._labs_key.public_key_bytes)

        # Write delivery manifest
        manifest = {
            "provisioned_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "bundle_id": bundle_id,
            "bundle_file": bundle_file.name,
            "token_file": token_file.name,
            "license_key_file": license_key_file.name,
            "deploy_pub_file": deploy_pub_file.name,
            "labs_pub_file": labs_pub_file.name,
            "deployment_fingerprint": deploy_key.fingerprint,
            "labs_fingerprint": self._labs_key.fingerprint,
            "licensee_id": licensee_id,
            "licensee_org": licensee_org,
            "risk_classification": risk_classification,
            "expires_in_days": expires_in_days,
            "delivery_note": (
                "SECURITY: license.key must be delivered out-of-band "
                "(USB, encrypted email, secure file transfer). "
                "All other files can be delivered over any channel."
            ),
        }
        manifest_file.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        return ProvisioningResult(
            bundle_path=str(bundle_file),
            token_path=str(token_file),
            license_key_path=str(license_key_file),
            deploy_pub_path=str(deploy_pub_file),
            labs_pub_path=str(labs_pub_file),
            manifest_path=str(manifest_file),
            agent_id=agent_id,
            bundle_id=bundle_id,
            deployment_fingerprint=deploy_key.fingerprint,
            labs_fingerprint=self._labs_key.fingerprint,
            licensee_id=licensee_id,
            licensee_org=licensee_org,
            risk_classification=risk_classification,
            expires_in_days=expires_in_days,
        )
