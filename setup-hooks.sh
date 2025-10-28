#!/bin/bash
#
# Setup script to install git hooks
#
# This script copies the pre-commit hook from .githooks/ to .git/hooks/
# and makes it executable.

set -e

echo "Setting up git hooks..."

# Copy pre-commit hook
if [ -f ".githooks/pre-commit" ]; then
    cp .githooks/pre-commit .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    echo "✓ Pre-commit hook installed"
else
    echo "✗ .githooks/pre-commit not found"
    exit 1
fi

echo ""
echo "Git hooks installed successfully!"
echo ""
echo "The pre-commit hook will automatically:"
echo "  - Format Python code with black"
echo "  - Sort imports with isort"
echo ""
echo "Make sure you have black and isort installed:"
echo "  pip install black isort"
