# Contributing to PimpMyRice

Thank you for your interest in contributing to PimpMyRice! This document provides guidelines and instructions for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip
- git

### Setting Up Development Environment

1. Clone the repository:
```bash
git clone https://github.com/daddodev/pimpmyrice.git
cd pimpmyrice
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/macOS
.venv\Scripts\activate    # On Windows
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Editor Setup

Set up your editor with the following tools:

- **pylsp**: For Python language server features like linting, autocompletion, and code navigation.
- **mypy**: For static type checking.
- **black**: For automatic code formatting.
- **pysort**: For sorting imports automatically.

Most modern editors (e.g., **VSCode**, **Neovim**, etc.) support these tools through extensions or LSP plugins. Ensure your editor is configured to use the virtual environment's Python interpreter to have access to the installed tools.

## Contributing Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Use the tools listed above for formatting and linting
- Keep code modular and maintainable

### Submitting Changes

1. Create a new branch for your feature:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and commit them:
```bash
git add .
git commit -m "Description of your changes"
```

3. Push to your fork:
```bash
git push origin feature/your-feature-name
```

4. Create a Pull Request on GitHub

## Bug Reports and Feature Requests

We use the GitHub Issues tracker for managing bugs and feature requests. Here’s how you can contribute:

- Bug Reports: When reporting a bug, please provide as much detail as possible, including:
    - Steps to reproduce the bug.
    - Expected behavior vs. actual behavior.
    - Any relevant log messages or error outputs.
- Feature Requests: When suggesting a new feature, please describe the problem you’re trying to solve, how the feature would improve the app, and why it would be useful.

Please make sure your issue has not already been reported by searching the issues list first.

## Need Help?

If you have questions, feel free to:

- Ask in our [Discord](https://discord.gg/TDrSB2wk6c)
- Check the [documentation](https://pimpmyrice.vercel.app/docs) 
- Open an issue
