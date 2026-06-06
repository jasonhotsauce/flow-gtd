# Native macOS Release Automation Setup

This guide configures the release path so pushing `release/v<version>` or
`release/<version>` runs build, test, package, GitHub release, and Homebrew
Cask publication.

The current workflow deploys the native app through Homebrew Cask. The app also
includes a first-party update checker that reads GitHub's latest release
metadata, compares it to the installed bundle version, and delegates update
installation to Homebrew.

This is an unsigned distribution path. It does not require an Apple Developer
account, Developer ID certificate, App Store Connect API key, or notarization.
The tradeoff is that macOS may show Gatekeeper trust warnings because the app is
not Developer ID signed or notarized.

## 1. Confirm The Release Source Of Truth

The release version is read from `pyproject.toml`:

```toml
version = "0.8.0"
```

The workflow requires the release branch name to match that version:

```bash
release/v0.8.0
# or
release/0.8.0
```

During the build, `scripts/build_native_app.sh` stamps this value into
`Flow.app/Contents/Info.plist` as `CFBundleShortVersionString`.

## 2. Create The Homebrew Tap

Create a tap repository, for example:

```text
github.com/<owner>/homebrew-flow
```

The workflow writes the rendered Cask to:

```text
Casks/flow-gtd.rb
```

If the tap repository is not `<owner>/homebrew-flow`, add a repository or
environment variable named:

```text
HOMEBREW_TAP_REPOSITORY=<owner>/<tap-repo>
```

## 3. Create A Write Deploy Key For The Tap

Create an SSH deploy key that can write only to the Homebrew tap repository.
This is narrower than a personal access token and avoids cross-repository PAT
scope mistakes.

Generate the key:

```bash
ssh-keygen -t ed25519 -C "flow-gtd-homebrew-release" -f ~/.ssh/flow_gtd_homebrew_release -N ""
```

Add the public key to the tap repository:

```text
homebrew-flow -> Settings -> Deploy keys -> Add deploy key
Title: Flow GTD release workflow
Key: contents of ~/.ssh/flow_gtd_homebrew_release.pub
Allow write access: enabled
```

Save the private key contents later as the source repository environment
secret:

```text
HOMEBREW_TAP_DEPLOY_KEY
```

## 4. Create The GitHub Release Environment

In the source repository:

```text
Settings -> Environments -> New environment
```

Create the environment:

```text
release
```

Recommended protection rules:

```text
Required reviewers: at least one release owner
Deployment branches/tags: Selected branches and tags
Allowed branch pattern: release/*
```

The repository setup currently has `jasonhotsauce` configured as the required
reviewer and `release/*` configured as the allowed deployment branch pattern.
If your GitHub plan exposes a "prevent self-review" toggle for environments,
enable it manually in the GitHub UI.

Add these as environment secrets on `release`:

```text
HOMEBREW_TAP_DEPLOY_KEY
```

Add this variable only if the tap is not `<owner>/homebrew-flow`:

```text
HOMEBREW_TAP_REPOSITORY
```

## 5. Check GitHub Actions Permissions

In the source repository:

```text
Settings -> Actions -> General
```

Confirm:

```text
Actions are allowed to run.
Workflow permissions allow the workflow to request contents: write.
```

The workflow itself defaults to `contents: read` and grants `contents: write`
only on the release job so it can create the GitHub release.

## 6. Cut A Release Branch

Update the version in `pyproject.toml`, then run local checks:

```bash
source .venv/bin/activate
pytest tests/unit -v
./scripts/test_native_app.sh
./scripts/build_native_app.sh
```

Commit the version bump and release changes.

Create the release branch with the matching version:

```bash
git switch -c release/v0.8.0
git push origin release/v0.8.0
```

Do not pre-create the GitHub release or tag. The workflow intentionally fails
if `v<version>` already exists.

## 7. Approve The Release Deployment

Open:

```text
GitHub -> Actions -> Release Native macOS App
```

Approve the `release` environment deployment when the workflow pauses.

After approval, the workflow:

1. Reads the version from `pyproject.toml`.
2. Verifies the branch name matches the version.
3. Fails if the GitHub release already exists.
4. Installs Python and Node dependencies.
5. Runs unit tests.
6. Runs native smoke tests.
7. Builds `.build/native/Flow.app`.
8. Packages the unsigned app archive.
9. Renders the Homebrew Cask with the archive SHA.
10. Creates the GitHub release.
11. Commits `Casks/flow-gtd.rb` to the Homebrew tap.

## 8. Verify The Published Release

Confirm the GitHub release exists:

```bash
gh release view v0.8.0 --repo <owner>/<source-repo>
```

Confirm the tap updated:

```bash
git clone https://github.com/<owner>/homebrew-flow.git /tmp/homebrew-flow
sed -n '1,80p' /tmp/homebrew-flow/Casks/flow-gtd.rb
```

Install as a user would:

```bash
brew tap <owner>/flow
brew install --cask flow-gtd
open -a "Flow GTD"
```

Validate the installed app state:

```bash
codesign -dvvv --entitlements :- "/Applications/Flow.app"
spctl -a -vv "/Applications/Flow.app"
```

Unsigned builds are expected to fail strict Developer ID assessment. That is the
accepted tradeoff for releasing without an Apple Developer account.

## 9. Update Behavior For Installed Users

Homebrew deployment updates the Cask. Users can update with:

```bash
brew update
brew upgrade --cask flow-gtd
```

Flow checks for updates automatically on launch, no more than once every six
hours. Users can also run:

```text
Flow GTD -> Check for Updates...
```

The update checker reads:

```text
https://api.github.com/repos/jasonhotsauce/flow-gtd/releases/latest
```

This URL is stored in `FlowReleaseFeedURL` in the app Info.plist and can be
overridden for testing with:

```bash
FLOW_UPDATE_CHECK_URL=https://example.test/latest.json open -a "Flow GTD"
```

When a newer release is available, Flow offers to install it. The install action
runs:

```bash
brew update
brew upgrade --cask flow-gtd || brew reinstall --cask flow-gtd
```

Flow quits while Homebrew replaces the app, then attempts to reopen Flow after
the update completes. The update log is written to:

```text
/tmp/flow-gtd-homebrew-update.log
```

This keeps the updater first-party and dependency-free. It requires Homebrew to
be present because Homebrew remains the install and update authority.
