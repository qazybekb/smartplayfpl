# Contributing to SmartPlay FPL

Thank you for your interest in contributing to SmartPlay FPL! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/qazybekb/smartplayfpl/issues)
2. If not, create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots if applicable
   - Environment details (OS, browser, etc.)

### Suggesting Features

1. Check existing issues for similar suggestions
2. Create a new issue with:
   - Clear description of the feature
   - Use case and benefits
   - Possible implementation approach

### Pull Requests

1. **Fork** the repository
2. **Clone** your fork locally
3. **Create** a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make** your changes
5. **Test** your changes thoroughly
6. **Commit** with clear messages:
   ```bash
   git commit -m "Add: description of feature"
   ```
7. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Open** a Pull Request

## Development Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Configure your .env file
./start_backend.sh
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Configure your .env.local file
npm run dev
```

## Code Style

### Python (Backend)

- Follow PEP 8 guidelines
- Use type hints where possible
- Write docstrings for functions and classes
- Keep functions focused and small

### TypeScript (Frontend)

- Use TypeScript strict mode
- Follow React best practices
- Use functional components with hooks
- Keep components small and reusable

## Commit Messages

Use clear, descriptive commit messages:

- `Add:` for new features
- `Fix:` for bug fixes
- `Update:` for updates to existing features
- `Remove:` for removed features
- `Refactor:` for code refactoring
- `Docs:` for documentation changes

## Questions?

Feel free to open an issue for any questions or reach out to the maintainer.

Thank you for contributing!
