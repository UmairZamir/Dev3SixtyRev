#!/bin/bash
# Run SDK tests after fixes

cd /Users/umairzamir/LocalDocuments/Dev3SixtyRev

# Clear any cached bytecode
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Run the tests
python -m pytest tests/unit/ -v --tb=short 2>&1 | head -150
