#!/bin/bash
# JARVIS Rust Speed Layer — Server Build & Install Script
# Run this on your Linux server after git pull
# Usage: bash install_rust.sh

set -e

echo "======================================"
echo "🦀 JARVIS Rust Speed Layer — Build"
echo "======================================"

# 1. Install Rust if not present
if ! command -v cargo &> /dev/null; then
    echo "📦 Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    echo "✅ Rust installed: $(rustc --version)"
else
    echo "✅ Rust already installed: $(rustc --version)"
fi

# 2. Install maturin
echo ""
echo "📦 Installing maturin..."
pip install maturin --quiet
echo "✅ maturin installed: $(maturin --version)"

# 3. Build & install the Rust wheel
echo ""
echo "🔨 Building jarvis_rust (release mode)..."
cd jarvis_rust
maturin develop --release
echo "✅ jarvis_rust installed!"

# 4. Run benchmark to verify
echo ""
echo "🧪 Running benchmark..."
python benchmark.py

echo ""
echo "======================================"
echo "✅ JARVIS Rust Speed Layer READY!"
echo "   Import with: import jarvis_rust"
echo "======================================"
