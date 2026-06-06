# Flow GTD - Makefile for native macOS app distribution
# Usage: make help

# ============================================================================
# Configuration
# ============================================================================
GITHUB_USER ?= $(or $(shell git config --get remote.origin.url 2>/dev/null | sed -E 's|^git@github.com:||; s|^https://github.com/||; s|/.*||'),YOUR_GITHUB_USERNAME)
GITHUB_REPO := flow-gtd
HOMEBREW_TAP_REPO := homebrew-flow
RELEASE_ARCH ?= $(shell uname -m)
NORMALIZED_RELEASE_ARCH := $(shell printf '%s\n' "$(RELEASE_ARCH)" | sed -e 's/^aarch64$$/arm64/' -e 's/^amd64$$/x86_64/')

# Extract version from pyproject.toml
VERSION := $(shell grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
RELEASE_ASSET := Flow-$(VERSION)-macos-$(NORMALIZED_RELEASE_ARCH).zip
RELEASE_ASSET_PATH := dist/$(RELEASE_ASSET)
RELEASE_ASSET_URL := https://github.com/$(GITHUB_USER)/$(GITHUB_REPO)/releases/download/v$(VERSION)/$(RELEASE_ASSET)

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
	@echo "$(BLUE)Flow GTD$(RESET) - Makefile for native macOS app distribution"
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
.PHONY: build-python
build-python: clean ## Build legacy Python wheel and sdist
	@echo "$(YELLOW)Building legacy Python package...$(RESET)"
	poetry build
	@echo "$(GREEN)Build complete. Artifacts in dist/$(RESET)"
	@ls -la dist/

.PHONY: build
build: build-native ## Build native macOS app bundle

.PHONY: build-native
build-native: ## Build native macOS app bundle with scripts/build_native_app.sh
	@echo "$(YELLOW)Building native macOS app...$(RESET)"
	./scripts/build_native_app.sh
	@echo "$(GREEN)Native app build complete.$(RESET)"

.PHONY: test-native
test-native: ## Run native Swift smoke tests with scripts/test_native_app.sh
	@echo "$(YELLOW)Running native smoke tests...$(RESET)"
	./scripts/test_native_app.sh
	@echo "$(GREEN)Native smoke tests complete.$(RESET)"

.PHONY: native-release-archive
native-release-archive: build-native ## Package Flow.app as a Homebrew Cask release zip
	@echo "$(YELLOW)Packaging native release archive...$(RESET)"
	FLOW_RELEASE_VERSION="$(VERSION)" FLOW_RELEASE_ARCH="$(NORMALIZED_RELEASE_ARCH)" ./scripts/package_native_app.sh

.PHONY: native-release-archive-signed
native-release-archive-signed: build-native ## Package signed Flow.app for public release
	@echo "$(YELLOW)Packaging signed native release archive...$(RESET)"
	FLOW_REQUIRE_SIGNED=1 FLOW_RELEASE_VERSION="$(VERSION)" FLOW_RELEASE_ARCH="$(NORMALIZED_RELEASE_ARCH)" ./scripts/package_native_app.sh

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
release: release-preflight native-release-archive ## Create GitHub release with native app zip asset (requires gh CLI)
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
	@echo "$(YELLOW)Creating GitHub release with $(RELEASE_ASSET)...$(RESET)"
	gh release create "v$(VERSION)" \
		"$(RELEASE_ASSET_PATH)" \
		--title "v$(VERSION)" \
		--notes "Release v$(VERSION)" \
		--generate-notes
	@echo "$(GREEN)Release v$(VERSION) created successfully!$(RESET)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(RESET)"
	@echo "  1. Run: make brew-cask"
	@echo "  2. Copy the cask to: $(HOMEBREW_TAP_REPO)/Casks/flow-gtd.rb"
	@echo "  3. Commit and push the cask"

.PHONY: release-preflight
release-preflight: ## Fail early if the release tag already exists
	@if [ -n "$$(git status --porcelain --untracked-files=all)" ]; then \
		echo "$(RED)Error: working tree is dirty. Commit or remove changes before releasing.$(RESET)"; \
		git status --short --untracked-files=all; \
		exit 1; \
	fi
	@if git rev-parse -q --verify "refs/tags/v$(VERSION)" >/dev/null; then \
		echo "$(RED)Error: local tag v$(VERSION) already exists. Bump the version before releasing.$(RESET)"; \
		exit 1; \
	fi
	@if git ls-remote --exit-code --tags origin "refs/tags/v$(VERSION)" >/dev/null 2>&1; then \
		echo "$(RED)Error: remote tag v$(VERSION) already exists. Bump the version before releasing.$(RESET)"; \
		exit 1; \
	fi

.PHONY: release-dry
release-dry: ## Show what release would do (dry run)
	@echo "$(YELLOW)Dry run - would create release v$(VERSION)$(RESET)"
	@echo ""
	@echo "Commands that would be executed:"
	@echo "  ./scripts/build_native_app.sh"
	@echo "  FLOW_RELEASE_VERSION=\"$(VERSION)\" FLOW_RELEASE_ARCH=\"$(NORMALIZED_RELEASE_ARCH)\" ./scripts/package_native_app.sh"
	@echo "  git tag -a \"v$(VERSION)\" -m \"Release v$(VERSION)\""
	@echo "  git push origin \"v$(VERSION)\""
	@echo "  gh release create \"v$(VERSION)\" \"$(RELEASE_ASSET_PATH)\" --title \"v$(VERSION)\" --generate-notes"

# ============================================================================
# Homebrew
# ============================================================================
.PHONY: brew-cask
brew-cask: ## Generate Homebrew Cask from the GitHub release asset
	@echo "$(YELLOW)Generating Homebrew Cask for v$(VERSION)...$(RESET)"
	@TMP_ARCHIVE=$$(mktemp); \
	trap 'rm -f "$$TMP_ARCHIVE"' EXIT; \
	echo "$(YELLOW)Downloading $(RELEASE_ASSET_URL) to compute SHA256...$(RESET)"; \
	if ! curl -fL "$(RELEASE_ASSET_URL)" -o "$$TMP_ARCHIVE"; then \
		echo "$(RED)Error: Could not download native release asset.$(RESET)"; \
		echo "URL: $(RELEASE_ASSET_URL)"; \
		exit 1; \
	fi; \
	echo "$(BLUE)═══════════════════════════════════════════════════════════════$(RESET)"; \
	echo "$(BLUE)Copy this cask to: $(HOMEBREW_TAP_REPO)/Casks/flow-gtd.rb$(RESET)"; \
	echo "$(BLUE)═══════════════════════════════════════════════════════════════$(RESET)"; \
	echo ""; \
	python3 scripts/render_homebrew_cask.py \
			--version "$(VERSION)" \
			--github-user "$(GITHUB_USER)" \
			--github-repo "$(GITHUB_REPO)" \
			--archive "$$TMP_ARCHIVE" \
			--arch "$(NORMALIZED_RELEASE_ARCH)"

.PHONY: brew-cask-local
brew-cask-local: ## Generate Homebrew Cask from an existing local native release archive
	@echo "$(YELLOW)Generating Homebrew Cask from local native archive...$(RESET)"
	@if [ ! -f "$(RELEASE_ASSET_PATH)" ]; then \
		echo "$(RED)Error: missing $(RELEASE_ASSET_PATH). Run make native-release-archive first.$(RESET)"; \
		exit 1; \
	fi
	@python3 scripts/render_homebrew_cask.py \
		--version "$(VERSION)" \
		--github-user "$(GITHUB_USER)" \
		--github-repo "$(GITHUB_REPO)" \
		--archive "$(RELEASE_ASSET_PATH)" \
		--arch "$(NORMALIZED_RELEASE_ARCH)"

.PHONY: brew-formula
brew-formula: brew-cask ## Deprecated alias for brew-cask
	@echo "$(YELLOW)brew-formula is deprecated; Flow GTD now ships as a Homebrew Cask.$(RESET)"

.PHONY: brew-formula-local
brew-formula-local: brew-cask-local ## Deprecated alias for brew-cask-local
	@echo "$(YELLOW)brew-formula-local is deprecated; Flow GTD now ships as a Homebrew Cask.$(RESET)"

# ============================================================================
# Full Release Workflow
# ============================================================================
.PHONY: publish
publish: test-unit test-native release-preflight release brew-cask ## Full native release: test, package, release, generate cask
	@echo ""
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(RESET)"
	@echo "$(GREEN)Release v$(VERSION) complete!$(RESET)"
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(RESET)"
	@echo ""
	@echo "$(YELLOW)Final steps:$(RESET)"
	@echo "  1. Copy the cask above to: $(HOMEBREW_TAP_REPO)/Casks/flow-gtd.rb"
	@echo "  2. Commit and push to your homebrew tap repository"
	@echo "  3. Users can then install with:"
	@echo "     brew tap $(GITHUB_USER)/flow"
	@echo "     brew install --cask flow-gtd"

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

.PHONY: worktree-setup
worktree-setup: ## Create a local .venv for WORKTREE using main's dependency files
	@if [ -z "$(WORKTREE)" ]; then \
		echo "$(RED)Error: WORKTREE is required.$(RESET)"; \
		echo "Usage: make worktree-setup WORKTREE=<main-or-sibling-folder>"; \
		exit 1; \
	fi
	bash ./scripts/setup_worktree_env.sh "$(WORKTREE)"
