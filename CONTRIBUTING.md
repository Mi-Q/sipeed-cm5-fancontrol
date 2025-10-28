# Contributing to Sipeed CM5 Fan Control

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Mi-Q/sipeed-cm5-fancontrol.git
   cd sipeed-cm5-fancontrol
   ```

2. Set up Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   cd deploy-systemd
   pip install -r requirements.txt
   pip install pytest pytest-cov flake8 pylint black isort
   ```

4. Set up git hooks (optional but recommended):
   ```bash
   cd ..
   ./setup-hooks.sh
   ```
   
   This installs a pre-commit hook that automatically formats code with black and isort.

## Testing

Run the test suite before submitting changes:

```bash
cd deploy-systemd
python -m pytest tests/ -v --cov=. --cov-report=term
```

Ensure code coverage remains above 80%.

## Code Style

This project follows PEP 8 style guidelines:

```bash
# Format code
black fan_control.py temp_exporter.py

# Sort imports
isort fan_control.py temp_exporter.py

# Check style
flake8 fan_control.py temp_exporter.py

# Run linter
pylint fan_control.py temp_exporter.py
```

## Commit Messages

Follow conventional commit format:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

Example:
```
feat: add support for custom temperature aggregation methods

- Implement min/max/avg aggregation for peer temperatures
- Add --aggregate CLI argument
- Update tests for new functionality
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linters
5. Commit your changes with descriptive messages
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request with:
   - Clear description of changes
   - Related issue numbers (if applicable)
   - Test results

## Release Process

### For Maintainers

1. **Update Version Numbers:**
   ```bash
   # Update VERSION file
   echo "0.3.0" > VERSION
   
   # Update version in Python files
   # - deploy-systemd/fan_control.py (Version: line)
   # - deploy-systemd/temp_exporter.py (Version: line)
   ```

2. **Update CHANGELOG.md:**
   ```markdown
   ## [0.3.0] - 2025-11-01
   
   ### Added
   - New feature descriptions
   
   ### Changed
   - Changes to existing functionality
   
   ### Fixed
   - Bug fixes
   
   [0.3.0]: https://github.com/Mi-Q/sipeed-cm5-fancontrol/compare/v0.2.0...v0.3.0
   ```

3. **Create Git Tag:**
   ```bash
   git add VERSION CHANGELOG.md deploy-systemd/*.py
   git commit -m "chore: bump version to 0.3.0"
   git tag -a v0.3.0 -m "Release version 0.3.0"
   git push origin main
   git push origin v0.3.0
   ```

4. **Create GitHub Release:**
   - Go to GitHub Releases
   - Click "Create a new release"
   - Select the tag (v0.3.0)
   - Title: `v0.3.0`
   - Description: Copy relevant sections from CHANGELOG.md
   - Attach any release artifacts if needed
   - Publish release

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (x.0.0): Breaking changes, incompatible API modifications
- **MINOR** (0.x.0): New features, backwards-compatible additions
- **PATCH** (0.0.x): Bug fixes, backwards-compatible changes

## Questions?

Feel free to open an issue for:
- Bug reports
- Feature requests
- Questions about usage or development

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
