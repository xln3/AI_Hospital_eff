#!/bin/bash
# Install dependencies for eval_unified.py

echo "Installing required packages for eval_unified.py..."
echo ""

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo "[ERROR] pip not found. Please install pip first."
    exit 1
fi

# Install all dependencies
echo "Running: pip install openai jsonlines numpy bootstrapped fuzzywuzzy python-Levenshtein prettytable tqdm xlrd"
pip install openai jsonlines numpy bootstrapped fuzzywuzzy python-Levenshtein prettytable tqdm xlrd -q

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All dependencies installed successfully!"
    echo ""
    echo "Installed packages:"
    echo "  - openai (for API integration)"
    echo "  - jsonlines (for JSONL file handling)"
    echo "  - numpy (for numerical operations)"
    echo "  - bootstrapped (for bootstrap confidence intervals)"
    echo "  - fuzzywuzzy (for fuzzy string matching)"
    echo "  - python-Levenshtein (for efficient fuzzy matching)"
    echo "  - prettytable (for formatted output)"
    echo "  - tqdm (for progress bars)"
    echo "  - xlrd (for reading ICD-10 database files)"
    echo ""
    echo "You can now run:"
    echo "  python evaluate/eval_unified.py --help"
else
    echo "[ERROR] Installation failed. Please install manually:"
    echo "  pip install openai jsonlines numpy bootstrapped fuzzywuzzy python-Levenshtein prettytable tqdm xlrd"
    exit 1
fi
