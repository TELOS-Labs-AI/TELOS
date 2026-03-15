# Hardware Requirements for TELOS Observatory

This document specifies the hardware requirements for running TELOS Observatory and reproducing validation results.

---

## Minimum Requirements

| Component | Specification |
|-----------|--------------|
| **CPU** | 4 cores (x86_64 or ARM64) |
| **RAM** | 8 GB |
| **Disk** | 10 GB free space |
| **Python** | 3.8 - 3.11 |
| **Network** | Internet connection (for API calls) |

**Suitable for:**
- Running TELOS Observatory demo
- Small-scale testing (< 100 attacks)
- Development and debugging

---

## Recommended Requirements

| Component | Specification |
|-----------|--------------|
| **CPU** | 8+ cores |
| **RAM** | 16 GB |
| **Disk** | 50 GB free space (SSD recommended) |
| **Python** | 3.10 or 3.11 |
| **GPU** | Optional (CUDA-capable for accelerated embeddings) |

**Suitable for:**
- Full validation reproduction (1,300+ attacks)
- Running complete benchmark suites
- Research and development

---

## Validation Reproduction Requirements

For reproducing the adversarial validation results from Zenodo (DOI: 10.5281/zenodo.18370659):

| Component | Requirement |
|-----------|-------------|
| **RAM** | 16 GB minimum (embedding model loading) |
| **Disk** | 20 GB (validation data + embeddings cache) |
| **Ollama** | Required for local embeddings |
| **Time** | ~45 minutes for 1,300 attacks |

### Ollama Setup

The validation requires Ollama for local embedding generation:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required model
ollama pull nomic-embed-text:latest
```

### Expected Execution Times

| Benchmark | Attacks | Expected Time | Hardware Used |
|-----------|---------|---------------|---------------|
| MedSafetyBench | 900 | ~30 min | MacBook Pro M2, 16GB |
| HarmBench | 400 | ~15 min | MacBook Pro M2, 16GB |
| **Total** | 1,300 | ~45 min | |

*Times may vary based on hardware configuration and Ollama API response times.*

---

## Operating System Compatibility

| OS | Status | Notes |
|----|--------|-------|
| macOS 12+ | Tested | Primary development platform |
| Ubuntu 20.04+ | Tested | Recommended for deployment |
| Windows 10+ | Untested | WSL2 recommended |

---

## GPU Acceleration (Optional)

GPU acceleration is optional but recommended for large-scale validation:

| Framework | Requirements |
|-----------|--------------|
| **PyTorch CUDA** | NVIDIA GPU with CUDA 11.7+ |
| **Apple Silicon** | MPS acceleration automatic on M1/M2/M3 |

To enable GPU:
```bash
# NVIDIA
pip install torch --index-url https://download.pytorch.org/whl/cu117

# Apple Silicon (automatic)
# PyTorch uses MPS by default on Apple Silicon
```

---

## API Requirements

The following external APIs are required:

| Service | Purpose | Rate Limits |
|---------|---------|-------------|
| **Mistral API** | LLM responses + embeddings | Standard tier sufficient |
| **Ollama** (local) | Validation embeddings | No limits (local) |

### API Key Setup

```bash
# Create .env file
echo "MISTRAL_API_KEY=your_key_here" > .env
```

---

## Memory Profiling

Approximate memory usage during validation:

| Phase | Peak RAM |
|-------|----------|
| Embedding model load | 2-4 GB |
| Batch embedding (64) | 4-6 GB |
| Full validation run | 8-12 GB |

---

## Disk Space Breakdown

| Component | Size |
|-----------|------|
| TELOS codebase | ~100 MB |
| Validation datasets | ~500 MB |
| Embedding cache | ~2 GB |
| Ollama models | ~5 GB |
| Logs and results | ~1 GB |
| **Total** | ~10 GB minimum |

---

## Troubleshooting

### Out of Memory
- Reduce batch size in embedding calls
- Close other applications
- Use swap/virtual memory

### Slow Embedding Generation
- Ensure Ollama is running locally
- Check network latency to API endpoints
- Consider GPU acceleration

### Ollama Connection Errors
```bash
# Verify Ollama is running
ollama list

# Restart if needed
ollama serve
```

---

## Zenodo Dataset Access

Validation datasets are available on Zenodo:

- **Adversarial Validation Dataset**: [10.5281/zenodo.18370659](https://doi.org/10.5281/zenodo.18370659)
- **Governance Benchmark Dataset**: [10.5281/zenodo.18009153](https://doi.org/10.5281/zenodo.18009153)

---

*Last updated: 2025-12-21*
