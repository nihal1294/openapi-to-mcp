# 🤝 Contributing to OpenAPI to MCP Server Generator

Thank you for your interest in contributing to the OpenAPI to MCP Server Generator! This document provides guidelines and instructions for contributing to this project.

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [Getting Started](#-getting-started)
- [Development Environment Setup](#-development-environment-setup)
- [Project Structure](#-project-structure)
- [Development Workflow](#-development-workflow)
- [Pull Request Process](#-pull-request-process)
- [Reporting Bugs](#-reporting-bugs)
- [Feature Requests](#-feature-requests)
- [Coding Standards](#-coding-standards)
- [Testing Guidelines](#-testing-guidelines)
- [Documentation](#-documentation)
- [Community](#-community)

## 📜 Code of Conduct

By participating in this project, you agree to abide by the following guidelines:

- Be respectful in your communications
- Value different viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what's best for the project and community
- Show empathy towards other community members

## 🚀 Getting Started

Before you begin contributing, please:

1. **Fork the repository** on GitHub
2. **Clone your fork** to your local machine
3. **Set up your development environment** (see next section)

## 💻 Development Environment Setup

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- Node.js 20+ (for testing generated code)
- Git

### Setting Up

1. Navigate to the project directory:
   ```bash
   cd openapi-to-mcp
   ```

2. Install dependencies with development tools:
   ```bash
   poetry install
   ```

## 📁 Project Structure

Here's an overview of the key directories and files in the project:

```
openapi-to-mcp/
├── docs/               # Documentation files
├── openapi_to_mcp/     # Main source code
├── templates/          # Jinja templates for code generation
├── tests/              # Test files
├── pyproject.toml      # Poetry configuration and dependencies
├── README.md           # Project documentation
└── LICENSE             # Apache License 2.0
```

## 🔄 Development Workflow

We use Poetry and poethepoet to manage development tasks. Inside the Poetry virtual environment:

### Code Formatting

Format your code with Ruff:

```bash
poetry run poe format
```

### Linting

Check your code for style issues and automatically fix them:

```bash
poetry run poe lint
```

### Running Tests

Run unit and integration tests with coverage:

```bash
poetry run poe test
```

### Running All Checks

Run formatting, linting, and testing in one command:

```bash
poetry run poe check
```

### Cleaning Temporary Files

Remove temporary files and build artifacts:

```bash
poetry run poe clean
```

## 🔄 Pull Request Process

1. **Create a branch** with a descriptive name:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   or
   ```bash
   git checkout -b fix/issue-you-are-fixing
   ```

2. **Make your changes** and commit them with clear, concise messages that explain the changes you've made.

3. **Test your changes:** Ensure to test your changes thoroughly so that you don't break existing functionality. Test your changes with real samples and also update the tests, and ensure all the tests pass:
   ```bash
   poetry run poe test
   ```

4. **Update documentation** if your changes affect the functionality, or require changes to the README.

5. **Push your changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Submit a pull request** to the main repository's `master` branch.

7. **Respond to feedback** during the review process.

### Pull Request Requirements

All pull requests should:

- Have a clear, descriptive title
- Include a description of what the changes do and why they are needed
- Have Copilot review the code
- Pass all automated checks (linting, tests)
- Address a single concern (feature, bugfix, etc.)
- Include tests for new functionality
- Update documentation as needed

## 🐛 Reporting Bugs

When reporting bugs, please include:

1. A clear, descriptive title
2. Detailed steps to reproduce the issue
3. What you expected to happen vs. what actually happened
4. Your environment (OS, Python version, Node.js version)
5. Any relevant logs or error messages

## 💡 Feature Requests

For feature requests, please describe:

1. What the feature should do
2. Why this feature would be useful
3. How you envision it working
4. Any alternatives you've considered

## 📝 Coding Standards

This project follows these coding standards:

- **Python**: We use Ruff for formatting and linting
- **TypeScript**: For generated code, follows standard TypeScript conventions, and ensure typesafety
- **Documentation**: Clear comments for complex code, docstrings for functions/classes
- **Testing**: All new code should have appropriate tests

### Python Specific Guidelines

- Use type hints for function parameters and return types
- Write docstrings using Google style format
- Use descriptive variable names
- Keep functions small and focused on a single task

## 🧪 Testing Guidelines

- Write unit tests for new functionality
- Ensure tests are deterministic (same input produces same output)
- Mock external dependencies
- Use meaningful test names that describe what is being tested
- Include both positive and negative test cases

### Testing Scope

- Unit tests for individual functions
- Integration tests for API operations
- End-to-end tests for the code generation functionality

## 📚 Documentation

Good documentation is crucial for this project. Please:

- Keep the **README** updated
- Add comments to explain complex code but keep them concise and relevant
- Ideally, write code that is self-explanatory, so that it doesn't need comments
- Include docstrings for functions and classes
- Document any command-line options in the help text
- Consider adding examples for non-trivial use cases

## 👥 Community

- **Questions**: Open an issue labeled "question" for any queries
- **Discussions**: Use GitHub Discussions for architectural or design discussions
- **Help**: Feel free to reach out to maintainers for guidance

## 📘 License

By contributing to this project, you agree that your contributions will be licensed under the Apache License 2.0, as stated in the [LICENSE](LICENSE) file.

Thank you for contributing to the OpenAPI to MCP Server Generator!
