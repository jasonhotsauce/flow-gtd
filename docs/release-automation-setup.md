# Native macOS Release Automation Setup

This guide configures the release path so pushing `release/v<version>` or
`release/<version>` runs build, test, package, sign, notarize, GitHub release,
and Homebrew Cask publication.

The current workflow deploys the native app through Homebrew Cask. The app also
includes a first-party update checker that reads GitHub's latest release
metadata, compares it to the installed bundle version, and delegates update
installation to Homebrew.

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

## 3. Create A Fine-Grained GitHub Token For The Tap

Create a fine-grained GitHub token that can write only to the Homebrew tap
repository.

Minimum access:

```text
Repository: <owner>/homebrew-flow
Contents: Read and write
```

Save this token later as:

```text
HOMEBREW_TAP_TOKEN
```

## 4. Export The Apple Developer ID Certificate

On the Mac that has the Developer ID Application certificate installed:

```bash
security find-identity -v -p codesigning
```

Copy the exact identity string, for example:

```text
Developer ID Application: Example LLC (TEAMID)
```

Export the certificate and private key from Keychain Access as a `.p12` file.
Use a strong export password.

Encode it for GitHub Secrets:

```bash
base64 -i DeveloperIDApplication.p12 | pbcopy
```

Save the copied value later as:

```text
APPLE_DEVELOPER_ID_CERTIFICATE_BASE64
```

Save the `.p12` export password as:

```text
APPLE_DEVELOPER_ID_CERTIFICATE_PASSWORD
```

Save the exact signing identity as:

```text
APPLE_CODESIGN_IDENTITY
```

## 5. Create The Apple Notarization API Key

In App Store Connect, create an API key that can be used by `notarytool`.
Download the `.p8` key once and keep it secure.

Record:

```text
Key ID
Issuer ID
```

Encode the key for GitHub Secrets:

```bash
base64 -i AuthKey_<KEYID>.p8 | pbcopy
```

Save the copied value later as:

```text
APPLE_NOTARY_KEY_BASE64
```

Save the other values as:

```text
APPLE_NOTARY_KEY_ID
APPLE_NOTARY_ISSUER_ID
```

## 6. Create The GitHub Release Environment

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
APPLE_DEVELOPER_ID_CERTIFICATE_BASE64
APPLE_DEVELOPER_ID_CERTIFICATE_PASSWORD
APPLE_CODESIGN_IDENTITY
APPLE_NOTARY_KEY_BASE64
APPLE_NOTARY_KEY_ID
APPLE_NOTARY_ISSUER_ID
HOMEBREW_TAP_TOKEN
```

Add this variable only if the tap is not `<owner>/homebrew-flow`:

```text
HOMEBREW_TAP_REPOSITORY
```

## 7. Check GitHub Actions Permissions

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

## 8. Cut A Release Branch

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

## 9. Approve The Release Deployment

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
5. Imports the Developer ID certificate into a temporary keychain.
6. Runs unit tests.
7. Runs native smoke tests.
8. Builds `.build/native/Flow.app`.
9. Signs and packages the app.
10. Submits the archive to Apple notarization.
11. Staples the notarization ticket.
12. Repackages the stapled app.
13. Renders the Homebrew Cask with the archive SHA.
14. Creates the GitHub release.
15. Commits `Casks/flow-gtd.rb` to the Homebrew tap.
16. Deletes temporary signing and notarization files.

## 10. Verify The Published Release

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

Validate the installed app:

```bash
codesign -dvvv --entitlements :- "/Applications/Flow.app"
spctl -a -vv "/Applications/Flow.app"
```

## 11. Update Behavior For Installed Users

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
