# Flow GTD - Makefile for Homebrew Distribution
# Usage: make help

# ============================================================================
# Configuration
# ============================================================================
GITHUB_USER ?= $(shell git config user.name 2>/dev/null || echo "YOUR_GITHUB_USERNAME")
GITHUB_REPO := flow-gtd
HOMEBREW_TAP_REPO := homebrew-flow

# Extract version from pyproject.toml
VERSION := $(shell grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')

# Colors for output
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# ============================================================================
# Help
# ============================================================================
.PHONY: help
help: ## Show this help message
	@echo "$(BLUE)Flow GTD$(RESET) - Makefile for Homebrew Distribution"
	@echo ""
	@echo "$(GREEN)Usage:$(RESET)"
	@echo "  make <target>"
	@echo ""
	@echo "$(GREEN)Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Current Version:$(RESET) $(VERSION)"

# ============================================================================
# Development
# ============================================================================
.PHONY: clean
clean: ## Remove build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(RESET)"
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info
	rm -rf flow_gtd.egg-info
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Clean complete.$(RESET)"

.PHONY: test
test: ## Run tests with pytest
	@echo "$(YELLOW)Running tests...$(RESET)"
	poetry run pytest tests/ -v
	@echo "$(GREEN)Tests complete.$(RESET)"

.PHONY: test-unit
test-unit: ## Run unit tests only
	@echo "$(YELLOW)Running unit tests...$(RESET)"
	poetry run pytest tests/unit -v
	@echo "$(GREEN)Unit tests complete.$(RESET)"

.PHONY: lint
lint: ## Run linter (ruff)
	@echo "$(YELLOW)Running linter...$(RESET)"
	poetry run ruff check flow/
	@echo "$(GREEN)Lint complete.$(RESET)"

.PHONY: format
format: ## Format code (ruff)
	@echo "$(YELLOW)Formatting code...$(RESET)"
	poetry run ruff format flow/
	@echo "$(GREEN)Format complete.$(RESET)"

# ============================================================================
# Build
# ============================================================================
.PHONY: build
build: clean ## Build wheel and sdist
	@echo "$(YELLOW)Building package...$(RESET)"
	poetry build
	@echo "$(GREEN)Build complete. Artifacts in dist/$(RESET)"
	@ls -la dist/

# ============================================================================
# Version Management
# ============================================================================
.PHONY: version
version: ## Show current version
	@echo "$(VERSION)"

.PHONY: bump-patch
bump-patch: ## Bump patch version (0.1.0 -> 0.1.1)
	@echo "$(YELLOW)Bumping patch version...$(RESET)"
	poetry version patch
	@echo "$(GREEN)New version: $$(poetry version -s)$(RESET)"

.PHONY: bump-minor
bump-minor: ## Bump minor version (0.1.0 -> 0.2.0)
	@echo "$(YELLOW)Bumping minor version...$(RESET)"
	poetry version minor
	@echo "$(GREEN)New version: $$(poetry version -s)$(RESET)"

.PHONY: bump-major
bump-major: ## Bump major version (0.1.0 -> 1.0.0)
	@echo "$(YELLOW)Bumping major version...$(RESET)"
	poetry version major
	@echo "$(GREEN)New version: $$(poetry version -s)$(RESET)"

# ============================================================================
# Release
# ============================================================================
.PHONY: release
release: ## Create GitHub release with tag (requires gh CLI)
	@echo "$(YELLOW)Creating release v$(VERSION)...$(RESET)"
	@if ! command -v gh &> /dev/null; then \
		echo "$(RED)Error: GitHub CLI (gh) is not installed.$(RESET)"; \
		echo "Install with: brew install gh"; \
		exit 1; \
	fi
	@if ! gh auth status &> /dev/null; then \
		echo "$(RED)Error: Not authenticated with GitHub CLI.$(RESET)"; \
		echo "Run: gh auth login"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Creating git tag v$(VERSION)...$(RESET)"
	git tag -a "v$(VERSION)" -m "Release v$(VERSION)"
	git push origin "v$(VERSION)"
	@echo "$(YELLOW)Creating GitHub release...$(RESET)"
	gh release create "v$(VERSION)" \
		--title "v$(VERSION)" \
		--notes "Release v$(VERSION)" \
		--generate-notes
	@echo "$(GREEN)Release v$(VERSION) created successfully!$(RESET)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(RESET)"
	@echo "  1. Run: make brew-formula"
	@echo "  2. Copy the formula to your homebrew-flow repo"
	@echo "  3. Commit and push the formula"

.PHONY: release-dry
release-dry: ## Show what release would do (dry run)
	@echo "$(YELLOW)Dry run - would create release v$(VERSION)$(RESET)"
	@echo ""
	@echo "Commands that would be executed:"
	@echo "  git tag -a \"v$(VERSION)\" -m \"Release v$(VERSION)\""
	@echo "  git push origin \"v$(VERSION)\""
	@echo "  gh release create \"v$(VERSION)\" --title \"v$(VERSION)\" --generate-notes"

# ============================================================================
# Homebrew
# ============================================================================
.PHONY: brew-formula
brew-formula: ## Generate Homebrew formula with SHA256
	@echo "$(YELLOW)Generating Homebrew formula for v$(VERSION)...$(RESET)"
	@echo ""
	@TARBALL_URL="https://github.com/$(GITHUB_USER)/$(GITHUB_REPO)/archive/refs/tags/v$(VERSION).tar.gz"; \
	echo "$(YELLOW)Downloading tarball to compute SHA256...$(RESET)"; \
	SHA256=$$(curl -sL "$$TARBALL_URL" | shasum -a 256 | cut -d' ' -f1); \
	if [ -z "$$SHA256" ] || [ "$$SHA256" = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" ]; then \
		echo "$(RED)Error: Could not download tarball. Make sure the release exists.$(RESET)"; \
		echo "URL: $$TARBALL_URL"; \
		exit 1; \
	fi; \
	echo "$(GREEN)SHA256: $$SHA256$(RESET)"; \
	echo ""; \
	echo "$(BLUE)═══════════════════════════════════════════════════════════════$(RESET)"; \
	echo "$(BLUE)Copy this formula to: $(HOMEBREW_TAP_REPO)/Formula/flow-gtd.rb$(RESET)"; \
	echo "$(BLUE)═══════════════════════════════════════════════════════════════$(RESET)"; \
	echo ""; \
	sed -e "s|{{VERSION}}|$(VERSION)|g" \
		-e "s|{{SHA256}}|$$SHA256|g" \
		-e "s|{{GITHUB_USER}}|$(GITHUB_USER)|g" \
		-e "s|{{GITHUB_REPO}}|$(GITHUB_REPO)|g" \
		homebrew/flow-gtd.rb.template

.PHONY: brew-formula-local
brew-formula-local: ## Generate formula from local tarball (for testing)
	@echo "$(YELLOW)Generating formula from local build...$(RESET)"
	@if [ ! -f "dist/flow_gtd-$(VERSION).tar.gz" ]; then \
		echo "$(YELLOW)Building package first...$(RESET)"; \
		$(MAKE) build; \
	fi
	@SHA256=$$(shasum -a 256 dist/flow_gtd-$(VERSION).tar.gz | cut -d' ' -f1); \
	echo "$(GREEN)SHA256: $$SHA256$(RESET)"; \
	echo ""; \
	echo "$(BLUE)Formula (using local path for testing):$(RESET)"; \
	sed -e "s|{{VERSION}}|$(VERSION)|g" \
		-e "s|{{SHA256}}|$$SHA256|g" \
		-e "s|{{GITHUB_USER}}|$(GITHUB_USER)|g" \
		-e "s|{{GITHUB_REPO}}|$(GITHUB_REPO)|g" \
		homebrew/flow-gtd.rb.template

# ============================================================================
# Full Release Workflow
# ============================================================================
.PHONY: publish
publish: test build release brew-formula ## Full release: test, build, release, generate formula
	@echo ""
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(RESET)"
	@echo "$(GREEN)Release v$(VERSION) complete!$(RESET)"
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(RESET)"
	@echo ""
	@echo "$(YELLOW)Final steps:$(RESET)"
	@echo "  1. Copy the formula above to: $(HOMEBREW_TAP_REPO)/Formula/flow-gtd.rb"
	@echo "  2. Commit and push to your homebrew tap repository"
	@echo "  3. Users can then install with:"
	@echo "     brew tap $(GITHUB_USER)/flow"
	@echo "     brew install flow-gtd"

# ============================================================================
# Installation (for development)
# ============================================================================
.PHONY: install
install: ## Install package in development mode
	@echo "$(YELLOW)Installing in development mode...$(RESET)"
	poetry install
	@echo "$(GREEN)Install complete.$(RESET)"

.PHONY: install-all
install-all: ## Install with all optional dependencies
	@echo "$(YELLOW)Installing with all LLM providers...$(RESET)"
	poetry install --extras "all-llm"
	@echo "$(GREEN)Install complete.$(RESET)"
