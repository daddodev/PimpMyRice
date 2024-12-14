# Contributing to PimpMyRice

Thank you for your interest in contributing to PimpMyRice! This document provides guidelines and instructions for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.8 or higher
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
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

### Building from Source

To build PimpMyRice from source:

1. Install build dependencies:
```bash
pip install build
```

2. Build the package:
```bash
python -m build
```

This will create both wheel (.whl) and source (.tar.gz) distributions in the `dist/` directory.

### Running Tests

```bash
pytest
```

## Contributing Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Write docstrings for functions and classes
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

### Creating Modules

If you're creating a new module:

1. Follow the [module documentation](https://pimpmyrice.vercel.app/docs/module)
2. Include proper documentation
3. Test your module thoroughly
4. Submit it to the [modules repository](https://pimpmyrice.vercel.app/modules)

## Bug Reports and Feature Requests

- Use the GitHub Issues tracker
- Provide detailed information about bugs
- For feature requests, explain the use case

## Code of Conduct

Please note that this project follows a Code of Conduct. By participating, you are expected to uphold this code.

## Questions?

If you have questions, feel free to:
- Open an issue
- Join our community discussions
- Check the [documentation](https://pimpmyrice.vercel.app/docs) 