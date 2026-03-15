"""
Data Export: Encrypted governance data export for audit and Intelligence Layer.

Exports governance session data (receipts, proofs, benchmark results) in
encrypted form. Supports two encryption modes:

1. **License-key encryption** (crypto_layer.py): For at-rest storage of
   governance data bound to a specific deployment. Decryptable by anyone
   with the license key.

2. **Session-key encryption** (TKeys): For session-bound data that should
   only be readable by the TELOS Intelligence Layer with the master key.

Regulatory alignment (self-assessed):
- NIST AI RMF (MANAGE 3.2): Encrypted export enables secure transfer of governance
  performance data for continuous improvement without exposing proprietary configs.
- IEEE P7002 (Data Privacy Process): Privacy-preserving export formats designed to
  support customer data protection while enabling TELOS Labs embedding calibration.
- NIST AI 600-1 (MEASURE 2.5): Exported telemetry designed to support NIST 600-1's
  requirement for documented, ongoing GenAI performance measurement data.
- FedRAMP SI-7: Version-tagged export formats with authenticated encryption
  designed to support information integrity during transfer and storage.

Export formats:
- `.telos-export` -- Encrypted JSON blob (version-tagged, single file)
- `.telos-proof`  -- Encrypted session proof (signed receipt chain)

Wire format:
    [1 byte]  format version (0x01)
    [1 byte]  encryption mode (0x01=license, 0x02=session)
    [N bytes] encrypted payload (crypto_layer format or TKeys format)

Usage:
    from telos_governance.data_export import GovernanceExporter

    exporter = GovernanceExporter(license_key=key)
    exporter.export_session_proof(proof, "output.telos-proof")
    exporter.export_benchmark_results(results, "output.telos-export")

    # Decrypt
    data = GovernanceExporter.decrypt_export(path, license_key=key)
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from telos_governance.crypto_layer import (
    ConfigEncryptor,
    ConfigEncryptionError,
    encrypt_config_file,
    decrypt_config_file,
)
from telos_governance.receipt_signer import GovernanceReceipt


# Export format constants
_EXPORT_VERSION = b'\x01'
_MODE_LICENSE = b'\x01'
_MODE_SESSION = b'\x02'
_EXPORT_HEADER_LEN = 2  # version + mode


class ExportError(Exception):
    """Raised when export or import fails."""
    pass


class GovernanceExporter:
    """Encrypted governance data exporter.

    Uses crypto_layer (AES-256-GCM + HKDF) for at-rest encryption of
    governance data. License key and optional agent_id provide access control.

    Args:
        license_key: License key material (>= 16 bytes) for encryption.
        agent_id: Optional agent identifier for AAD binding.
    """

    def __init__(self, license_key: bytes, agent_id: Optional[str] = None):
        self._encryptor = ConfigEncryptor(license_key)
        self._license_key = license_key
        self._agent_id = agent_id
        self._aad = agent_id.encode("utf-8") if agent_id else None

    def export_session_proof(
        self,
        proof: Dict[str, Any],
        output_path: Union[str, Path],
    ) -> Path:
        """Export an encrypted session proof.

        Args:
            proof: Session proof dict from GovernanceSessionContext.generate_proof().
            output_path: Path for the encrypted output file.

        Returns:
            Path to the written file.

        Raises:
            ExportError: If encryption or write fails.
        """
        return self._export_data(proof, output_path, data_type="session_proof")

    def export_benchmark_results(
        self,
        results: Dict[str, Any],
        output_path: Union[str, Path],
    ) -> Path:
        """Export encrypted benchmark results.

        Args:
            results: Benchmark results dict.
            output_path: Path for the encrypted output file.

        Returns:
            Path to the written file.

        Raises:
            ExportError: If encryption or write fails.
        """
        return self._export_data(results, output_path, data_type="benchmark_results")

    def export_receipts(
        self,
        receipts: List[GovernanceReceipt],
        output_path: Union[str, Path],
    ) -> Path:
        """Export encrypted governance receipts.

        Args:
            receipts: List of signed GovernanceReceipt objects.
            output_path: Path for the encrypted output file.

        Returns:
            Path to the written file.

        Raises:
            ExportError: If encryption or write fails.
        """
        data = {
            "receipts": [r.to_dict() for r in receipts],
            "count": len(receipts),
            "exported_at": time.time(),
        }
        return self._export_data(data, output_path, data_type="receipts")

    def _export_data(
        self,
        data: Dict[str, Any],
        output_path: Union[str, Path],
        data_type: str = "generic",
    ) -> Path:
        """Internal: serialize, encrypt, and write data.

        Args:
            data: Dict to export.
            output_path: Output file path.
            data_type: Type label for the export envelope.

        Returns:
            Path to the written file.
        """
        try:
            # Wrap in export envelope
            envelope = {
                "telos_export_version": 1,
                "data_type": data_type,
                "agent_id": self._agent_id,
                "exported_at": time.time(),
                "payload": data,
            }

            plaintext = json.dumps(envelope, default=str).encode("utf-8")
            encrypted = self._encryptor.encrypt(plaintext, aad=self._aad)

            # Write with export header
            output = Path(output_path)
            output.write_bytes(_EXPORT_VERSION + _MODE_LICENSE + encrypted)
            return output

        except ConfigEncryptionError as e:
            raise ExportError(f"Encryption failed: {e}") from e
        except (OSError, IOError) as e:
            raise ExportError(f"Write failed: {e}") from e

    # -------------------------------------------------------------------------
    # Decryption (static)
    # -------------------------------------------------------------------------

    @staticmethod
    def decrypt_export(
        path: Union[str, Path],
        license_key: bytes,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Decrypt an exported governance data file.

        Args:
            path: Path to the encrypted export file.
            license_key: License key material (must match encryption key).
            agent_id: Optional agent ID (must match if used during export).

        Returns:
            Decrypted export envelope dict with 'payload' containing the data.

        Raises:
            ExportError: If decryption fails.
        """
        try:
            raw = Path(path).read_bytes()

            if len(raw) < _EXPORT_HEADER_LEN + 45:  # header + min crypto_layer blob
                raise ExportError(f"Export file too short ({len(raw)} bytes)")

            version = raw[0:1]
            if version != _EXPORT_VERSION:
                raise ExportError(f"Unsupported export version: 0x{version.hex()}")

            mode = raw[1:2]
            if mode != _MODE_LICENSE:
                raise ExportError(f"Unsupported encryption mode: 0x{mode.hex()}")

            encrypted = raw[_EXPORT_HEADER_LEN:]
            aad = agent_id.encode("utf-8") if agent_id else None

            plaintext = decrypt_config_file(encrypted, license_key, agent_id=agent_id)
            return json.loads(plaintext.decode("utf-8"))

        except ConfigEncryptionError as e:
            raise ExportError(f"Decryption failed: {e}") from e
        except json.JSONDecodeError as e:
            raise ExportError(f"Corrupted export data: {e}") from e
        except (OSError, IOError) as e:
            raise ExportError(f"Read failed: {e}") from e
