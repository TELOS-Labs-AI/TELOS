"""
Fidelity Display Normalization
==============================

Maps SentenceTransformer raw scores to a normalized display scale that matches
user expectations (0.70+ = GREEN, 0.60+ = YELLOW, 0.50+ = ORANGE, <0.50 = RED).

CALIBRATION (2025-12-28 - CENTROID-BASED):
------------------------------------------
Updated for PA centroid embeddings. Each template PA now uses the centroid
(mean) of normalized embeddings from purpose/scope + 10 example_queries.
This creates a PA that covers the semantic space of aligned queries.

With centroid computation, raw similarities are lower but more meaningful:
- On-topic Turn 1 queries: ~0.50 raw → should be GREEN
- Related but drifting: ~0.35 raw → should be ORANGE
- Off-topic: ~0.20 raw → should be RED

ANCHOR POINTS (2025-12-28):
    Raw 0.50 → Display 0.70 (GREEN threshold) - on-topic Turn 1
    Raw 0.41 → Display 0.60 (YELLOW threshold)
    Raw 0.33 → Display 0.50 (ORANGE threshold)
    Raw 0.20 → Display 0.35 (RED zone)

Formula: display = 1.167 × raw + 0.117

Derivation:
    slope = (0.70 - 0.35) / (0.50 - 0.20) = 0.35 / 0.30 = 1.167
    intercept = 0.70 - 1.167 × 0.50 = 0.117
"""

from telos_core.constants import (
    ST_FIDELITY_GREEN, ST_FIDELITY_YELLOW, ST_FIDELITY_ORANGE
)

# Display thresholds (universal - what users expect)
DISPLAY_GREEN = 0.70
DISPLAY_YELLOW = 0.60
DISPLAY_ORANGE = 0.50

# Linear transformation coefficients (2025-12-28 CENTROID recalibration)
# Anchor points: raw 0.50→0.70 (GREEN), raw 0.20→0.35 (RED)
# m = (0.70 - 0.35) / (0.50 - 0.20) = 0.35 / 0.30 = 1.167
# b = 0.70 - 1.167 × 0.50 = 0.117
LINEAR_SLOPE = 1.167
LINEAR_INTERCEPT = 0.117

# AI Response calibration (2025-12-29)
# AI responses achieve lower raw cosine similarity (~0.40) vs USER_PA than queries (~0.57)
# because they're longer explanatory text vs short questions.
# Anchor points for AI responses vs USER_PA:
#   raw 0.40→0.70 (GREEN) - on-topic teaching response
#   raw 0.15→0.35 (RED)   - off-topic response
# m = (0.70 - 0.35) / (0.40 - 0.15) = 0.35 / 0.25 = 1.4
# b = 0.70 - 1.4 × 0.40 = 0.14
AI_RESPONSE_SLOPE = 1.4
AI_RESPONSE_INTERCEPT = 0.14


def normalize_st_fidelity(raw_fidelity: float) -> float:
    """
    Transform SentenceTransformer raw fidelity to display scale.

    Uses linear transformation calibrated 2025-12-28 for CENTROID PA embeddings:
        Raw 0.50 → Display 0.70 (GREEN threshold) - on-topic Turn 1
        Raw 0.41 → Display 0.60 (YELLOW threshold)
        Raw 0.33 → Display 0.50 (ORANGE threshold)
        Raw 0.20 → Display 0.35 (RED zone)
        Raw 0.10 → Display 0.23 (deep RED)

    With centroid embeddings (mean of purpose/scope + 10 example_queries),
    on-topic queries achieve ~0.50 raw similarity, not ~0.76 as before.

    Args:
        raw_fidelity: Raw cosine similarity from SentenceTransformer

    Returns:
        Normalized fidelity on display scale (0.0 to 1.0)

    Examples:
        >>> normalize_st_fidelity(0.508)  # "What is recursion?" - on-topic Turn 1
        0.71  # GREEN zone - aligned
        >>> normalize_st_fidelity(0.35)   # Related but drifting
        0.53  # ORANGE zone - minor drift
        >>> normalize_st_fidelity(0.10)   # Off-topic
        0.23  # RED zone - triggers intervention
    """
    display = LINEAR_SLOPE * raw_fidelity + LINEAR_INTERCEPT
    return max(0.0, min(1.0, display))  # Clamp to [0, 1]


def normalize_ai_response_fidelity(raw_fidelity: float) -> float:
    """
    Transform AI response raw fidelity to display scale.

    AI responses have lower raw cosine similarity than user queries when measured
    against the same PA, because AI responses are longer explanatory text while
    queries are short questions. This requires a different calibration.

    Calibration (2025-12-29):
        Raw 0.40 → Display 0.70 (GREEN threshold) - on-topic teaching response
        Raw 0.33 → Display 0.60 (YELLOW threshold) - minor drift response
        Raw 0.26 → Display 0.50 (ORANGE threshold) - drifting response
        Raw 0.15 → Display 0.35 (RED zone) - off-topic response

    Use this for AI fidelity in GREEN zone (measuring vs USER_PA for topical alignment).
    For intervention zone (measuring vs AI_PA for behavioral alignment), use
    normalize_st_fidelity since AI_PA centroids include example_ai_responses.

    Args:
        raw_fidelity: Raw cosine similarity from AI response vs USER_PA

    Returns:
        Normalized fidelity on display scale (0.0 to 1.0)

    Examples:
        >>> normalize_ai_response_fidelity(0.40)  # On-topic teaching response
        0.70  # GREEN zone
        >>> normalize_ai_response_fidelity(0.33)  # Minor drift response
        0.60  # YELLOW zone (minor drift)
        >>> normalize_ai_response_fidelity(0.26)  # Drifting response
        0.50  # ORANGE zone
        >>> normalize_ai_response_fidelity(0.15)  # Off-topic response
        0.35  # RED zone
    """
    display = AI_RESPONSE_SLOPE * raw_fidelity + AI_RESPONSE_INTERCEPT
    return max(0.0, min(1.0, display))  # Clamp to [0, 1]


def normalize_fidelity_for_display(
    raw_fidelity: float,
    model_type: str
) -> float:
    """
    Normalize any model's raw fidelity to the universal display scale.

    Both SentenceTransformer and Mistral embeddings produce similar raw
    cosine similarity ranges (~0.35-0.60 for typical content), so we apply
    the same linear transformation to both.

    CHANGE (2025-12-26): Previously Mistral scores were passed through raw,
    causing off-topic content (raw ~0.35-0.45) to display as 78-88% instead
    of the expected ~40% (RED zone). Now both models use normalization.

    Args:
        raw_fidelity: Raw cosine similarity from embedding model
        model_type: 'sentence_transformer' or 'mistral'

    Returns:
        Normalized fidelity for display (0.0 to 1.0)
    """
    # Apply same normalization to all embedding models
    # Both ST and Mistral produce similar raw similarity ranges
    return normalize_st_fidelity(raw_fidelity)


def get_display_thresholds() -> dict:
    """
    Get the universal display thresholds.
    """
    return {
        'green': DISPLAY_GREEN,
        'yellow': DISPLAY_YELLOW,
        'orange': DISPLAY_ORANGE,
    }


def raw_to_display_mapping_table() -> str:
    """
    Generate a mapping table for verification.
    """
    lines = [
        "SentenceTransformer Raw → Display Mapping (CENTROID CALIBRATION 2025-12-28)",
        "=" * 60,
        f"{'Raw':<10} {'Display':<10} {'Zone':<10}",
        "-" * 60,
    ]

    # Test values for centroid-based PA embeddings (lower raw scores)
    test_values = [0.60, 0.55, 0.508, 0.50, 0.45, 0.41, 0.38, 0.35, 0.33, 0.30, 0.25, 0.20, 0.15, 0.10, 0.00]

    for raw in test_values:
        display = normalize_st_fidelity(raw)
        if display >= DISPLAY_GREEN:
            zone = "GREEN"
        elif display >= DISPLAY_YELLOW:
            zone = "YELLOW"
        elif display >= DISPLAY_ORANGE:
            zone = "ORANGE"
        else:
            zone = "RED"
        lines.append(f"{raw:<10.3f} {display:<10.3f} {zone:<10}")

    lines.append("-" * 60)
    lines.append("Anchor points verified (2025-12-28 CENTROID):")
    lines.append(f"  ST 0.50 → {normalize_st_fidelity(0.50):.2f} (expect 0.70 GREEN threshold)")
    lines.append(f"  ST 0.41 → {normalize_st_fidelity(0.41):.2f} (expect ~0.60 YELLOW threshold)")
    lines.append(f"  ST 0.33 → {normalize_st_fidelity(0.33):.2f} (expect ~0.50 ORANGE threshold)")
    lines.append(f"  ST 0.20 → {normalize_st_fidelity(0.20):.2f} (expect 0.35 RED zone)")
    lines.append("Test case from centroid embeddings:")
    lines.append(f"  ST 0.508 → {normalize_st_fidelity(0.508):.2f} ('What is recursion?' - on-topic Turn 1)")

    return "\n".join(lines)


if __name__ == "__main__":
    print(raw_to_display_mapping_table())
