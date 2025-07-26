#!/bin/bash
# Run test suite with detailed output

echo "Installing test dependencies..."
pip install pytest pytest-cov

echo "Running API tests..."
pytest -xvs tests/test_memory_api.py

echo "Running real-time processing tests..."
pytest -xvs tests/test_realtime_processing.py

echo "Generating coverage report..."
pytest --cov=. tests/
