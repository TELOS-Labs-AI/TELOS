# Contributing to TELOS

Thank you for your interest in contributing to TELOS! This document provides guidelines for contributing to the project.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/TELOS-Labs-AI/telos.git
   cd telos
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your MISTRAL_API_KEY
   ```

5. **Run the application**
   ```bash
   export PYTHONPATH=$(pwd)
   streamlit run telos_observatory/main.py --server.port 8501
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=telos_core --cov=telos_governance --cov-report=html

# Run specific test file
pytest tests/test_fidelity_math.py -v
```

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/TELOS-Labs-AI/telos/issues)
2. If not, create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version)
   - Relevant logs or screenshots

### Suggesting Enhancements

1. Open an issue with the `enhancement` label
2. Describe the feature and its use case
3. Explain why this would benefit the project

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** following our code standards (below)
3. **Add tests** for any new functionality
4. **Update documentation** as needed
5. **Run the test suite** to ensure nothing is broken
6. **Submit a pull request** with a clear description

## Code Standards

### Python Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use meaningful variable and function names

### Docstrings

Use Google-style docstrings:

```python
def calculate_fidelity(embedding: np.ndarray, attractor: np.ndarray) -> float:
    """Calculate fidelity between embedding and primacy attractor.

    Args:
        embedding: The input embedding vector (1024-dim for Mistral).
        attractor: The primacy attractor center vector.

    Returns:
        Normalized fidelity score between 0.0 and 1.0.

    Raises:
        ValueError: If embedding dimensions don't match.
    """
```

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove, Refactor)
- Reference issues when applicable: `Fix #123: Correct fidelity calculation`

### Testing Requirements

- All new features must include tests
- Maintain or improve code coverage
- Tests should be deterministic and reproducible

## Project Structure

```
telos/
├── telos_core/               # Pure mathematical engine
├── telos_governance/         # Governance gates (conversational + agentic)
├── telos_gateway/            # FastAPI API gateway
├── telos_adapters/           # Framework adapters (LangGraph, generic)
├── telos_observatory/        # Streamlit UI
├── telos_privacy/            # TKeys cryptographic layer
├── telos_sql_agent/          # SQL agent reference
├── tests/                    # Unit, integration, validation tests
├── validation/               # Benchmark datasets
├── research/                 # Active research program
└── docs/                     # Documentation
```

## Research Contributions

TELOS is a research project. If you're contributing research:

1. **Mathematical contributions** should include proofs or empirical validation
2. **New governance mechanisms** should include adversarial testing
3. **Publications** should cite the TELOS Technical Paper

## Questions?

- Open an [Issue](https://github.com/TELOS-Labs-AI/telos/issues) with the `question` label
- Review the [Whitepaper](docs/TELOS_Whitepaper_v3.0.pdf) for mathematical foundations
- Review [CLAUDE.md](CLAUDE.md) for architecture and terminology
- Contact: contact@telos-labs.ai

## License

By contributing, you agree that your contributions will be licensed under the project's Apache License 2.0.
