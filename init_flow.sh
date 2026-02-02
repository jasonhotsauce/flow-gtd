#!/bin/bash

# ==========================================
# Project Flow - Structure Generator
# Based on: Canonical File Structure (v2.0)
# ==========================================

echo "🚀 Starting Project Flow initialization..."

# 1. 基础设施层 (Infrastructure)
# ------------------------------------------
echo "📂 Creating directory hierarchy..."

# Core Layers
mkdir -p flow/core
mkdir -p flow/models
mkdir -p flow/database
mkdir -p flow/sync
mkdir -p flow/utils

# Presentation Layer (CLI & TUI)
mkdir -p flow/tui/common/widgets
# TUI Screens (Component-Based)
mkdir -p flow/tui/screens/inbox
mkdir -p flow/tui/screens/action
mkdir -p flow/tui/screens/review

# Tests & Data
mkdir -p tests/{unit,integration}
mkdir -p data/knowledge_base

# 2. 核心文件生成 (File Generation)
# ------------------------------------------
echo "📄 Generating source files..."

# Root Level
touch pyproject.toml README.md

# Flow Root
touch flow/__init__.py flow/main.py flow/config.py flow/cli.py

# Logic Layer (Core)
touch flow/core/__init__.py
touch flow/core/engine.py   # Main Funnel Logic
touch flow/core/coach.py    # AI Socratic Logic
touch flow/core/rag.py      # Semantic Search

# Domain Layer (Models)
touch flow/models/__init__.py
touch flow/models/item.py   # Pydantic Schemas

# Persistence Layer (Database)
touch flow/database/__init__.py
touch flow/database/sqlite.py
touch flow/database/vectors.py

# Infrastructure Layer (Sync)
touch flow/sync/__init__.py
touch flow/sync/reminders.py

# Shared Kernel (Utils)
touch flow/utils/__init__.py
touch flow/utils/llm.py

# 3. TUI 组件生成 (TUI Components)
# ------------------------------------------
echo "🎨 Generating TUI components (Colocated Styles)..."

# TUI Root
touch flow/tui/__init__.py flow/tui/app.py

# Shared Resources
touch flow/tui/common/theme.tcss
touch flow/tui/common/widgets/__init__.py
touch flow/tui/common/widgets/card.py
touch flow/tui/common/widgets/sidecar.py

# Screen: Inbox (Capture)
touch flow/tui/screens/inbox/__init__.py
touch flow/tui/screens/inbox/inbox.py
touch flow/tui/screens/inbox/inbox.tcss

# Screen: Action (Execution)
touch flow/tui/screens/action/__init__.py
touch flow/tui/screens/action/action.py
touch flow/tui/screens/action/action.tcss

# Screen: Review (Wizard)
touch flow/tui/screens/review/__init__.py
touch flow/tui/screens/review/review.py
touch flow/tui/screens/review/review.tcss

# 4. 测试与配置 (Tests & Config)
# ------------------------------------------
echo "🧪 Generating test suite skeletons..."

touch tests/__init__.py
touch tests/conftest.py

# 5. Git Ignore (Bonus)
# ------------------------------------------
echo "🛡️ Generating .gitignore..."
cat <<EOT >> .gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.env

# Data (Local-First Privacy)
data/
*.db
*.sqlite

# Cursor (Optional: keep rules, ignore history)
.cursor/state/
EOT

echo "✅ Initialization Complete!"
echo "   - .cursor directory was preserved."
echo "   - TUI structure is component-based."
echo "   - Ready for 'poetry install'."