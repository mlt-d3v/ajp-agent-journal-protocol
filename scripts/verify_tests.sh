#!/bin/bash
# Verify AJP test suite
set -e
cd "$(dirname "$0")/../src"
python -m pytest ajp/tests/ -v --tb=short "$@"
