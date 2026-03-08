"""
AgentHarm HuggingFace Dataset Loader
======================================
Loads the AgentHarm dataset from HuggingFace and converts it
to the format expected by TELOSDefenseLayer.run_benchmark().

Dataset: https://huggingface.co/datasets/ai-safety-institute/AgentHarm

Configurations:
    - harmful: 176 test + 32 validation (44 base × 4 augmented)
    - harmless_benign: 176 test + 32 validation
    - chat: 44 test + 8 validation (prompt-only, no tools)

Categories (8):
    Disinformation, Harassment, Drugs, Fraud,
    Hate, Cybercrime, Sexual, Copyright

Usage:
    from validation.agentic.load_agentharm import load_agentharm_tasks
    harmful = load_agentharm_tasks(config="harmful", split="test_public")
    benign = load_agentharm_tasks(config="harmless_benign", split="test_public")
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# AgentHarm category mapping to TELOS safety boundary categories
CATEGORY_MAP = {
    "Disinformation": "disinformation",
    "Harassment": "harassment",
    "Drugs": "illegal_drugs",
    "Fraud": "fraud",
    "Hate": "harassment",  # Maps to harassment boundary
    "Cybercrime": "cybercrime",
    "Sexual": "csam",  # Closest safety boundary
    "Copyright": "copyright",
}


def load_agentharm_tasks(
    config: str = "harmful",
    split: str = "test_public",
    cache_dir: Optional[str] = None,
) -> List[Dict]:
    """
    Load AgentHarm tasks from HuggingFace and convert to benchmark format.

    Args:
        config: Dataset configuration ("harmful", "harmless_benign", "chat")
        split: Dataset split ("test_public", "validation")
        cache_dir: Optional cache directory for downloaded data

    Returns:
        List of task dicts with keys:
            - id: Task ID
            - name: Task name
            - category: Harm category
            - prompt: Task prompt text
            - target_functions: List of target function names (harmful only)
            - expected_blocked: Whether TELOS should block this task
    """
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError(
            "HuggingFace datasets library required. "
            "Install with: pip install datasets"
        )

    logger.info(f"Loading AgentHarm dataset: config={config}, split={split}")

    kwargs = {}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir

    dataset = load_dataset(
        "ai-safety-institute/AgentHarm",
        config,
        split=split,
        **kwargs,
    )

    tasks = []
    for row in dataset:
        task = {
            "id": row.get("id", ""),
            "name": row.get("name", ""),
            "category": row.get("category", "unknown"),
            "prompt": row.get("prompt", ""),
            "expected_blocked": config in ("harmful", "chat"),
        }

        # Extract target functions if available
        target_fns = row.get("target_functions")
        if target_fns:
            if isinstance(target_fns, str):
                try:
                    task["target_functions"] = json.loads(target_fns)
                except (json.JSONDecodeError, TypeError):
                    task["target_functions"] = [target_fns]
            elif isinstance(target_fns, list):
                task["target_functions"] = target_fns
            else:
                task["target_functions"] = []
        else:
            task["target_functions"] = []

        # Map category to TELOS boundary category
        task["telos_category"] = CATEGORY_MAP.get(
            task["category"], task["category"].lower()
        )

        tasks.append(task)

    logger.info(
        f"Loaded {len(tasks)} tasks from AgentHarm "
        f"(config={config}, split={split})"
    )

    return tasks


def load_agentharm_full(
    cache_dir: Optional[str] = None,
) -> Dict[str, List[Dict]]:
    """
    Load both harmful and benign task sets from AgentHarm.

    Returns:
        Dict with keys "harmful" and "benign", each containing
        a list of task dicts.
    """
    harmful = load_agentharm_tasks(
        config="harmful", split="test_public", cache_dir=cache_dir
    )
    benign = load_agentharm_tasks(
        config="harmless_benign", split="test_public", cache_dir=cache_dir
    )

    return {
        "harmful": harmful,
        "benign": benign,
    }


def load_agentharm_from_json(
    json_path: str,
    expected_blocked: bool = True,
) -> List[Dict]:
    """
    Load AgentHarm tasks from a local JSON file (offline mode).

    Useful when the HuggingFace dataset has been downloaded and
    saved locally, or for testing with custom task sets.

    Args:
        json_path: Path to JSON file with task list
        expected_blocked: Whether these tasks should be blocked

    Returns:
        List of task dicts in benchmark format
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"AgentHarm JSON not found: {json_path}")

    with open(path) as f:
        raw_tasks = json.load(f)

    # Handle both list and dict-with-behaviors format
    if isinstance(raw_tasks, dict):
        raw_tasks = raw_tasks.get("behaviors", raw_tasks.get("tasks", []))

    tasks = []
    for row in raw_tasks:
        task = {
            "id": row.get("id", ""),
            "name": row.get("name", ""),
            "category": row.get("category", "unknown"),
            "prompt": row.get("prompt", ""),
            "target_functions": row.get("target_functions", []),
            "expected_blocked": expected_blocked,
            "telos_category": CATEGORY_MAP.get(
                row.get("category", ""), row.get("category", "unknown").lower()
            ),
        }
        tasks.append(task)

    logger.info(f"Loaded {len(tasks)} tasks from {json_path}")
    return tasks
