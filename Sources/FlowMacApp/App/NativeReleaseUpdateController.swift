import AppKit
import Foundation

struct NativeReleaseVersion {
    let rawValue: String

    init(_ rawValue: String) {
        self.rawValue = rawValue.trimmingCharacters(in: CharacterSet(charactersIn: "vV \n\t"))
    }

    func isNewer(than other: NativeReleaseVersion) -> Bool {
        let lhs = numericComponents
        let rhs = other.numericComponents
        let count = max(lhs.count, rhs.count)

        for index in 0..<count {
            let left = index < lhs.count ? lhs[index] : 0
            let right = index < rhs.count ? rhs[index] : 0
            if left != right {
                return left > right
            }
        }
        return false
    }

    private var numericComponents: [Int] {
        rawValue
            .split(separator: ".")
            .map { component in
                let digits = component.prefix(while: { $0.isNumber })
                return Int(digits) ?? 0
            }
    }
}

struct NativeReleaseUpdate: Decodable {
    let tagName: String
    let htmlURL: URL?

    enum CodingKeys: String, CodingKey {
        case tagName = "tag_name"
        case htmlURL = "html_url"
    }
}

@MainActor
final class NativeReleaseUpdateController: ObservableObject {
    private let session: URLSession
    private let bundle: Bundle
    private let userDefaults: UserDefaults
    private let checkInterval: TimeInterval
    private var checkTask: Task<Void, Never>?

    init(
        session: URLSession = .shared,
        bundle: Bundle = .main,
        userDefaults: UserDefaults = .standard,
        checkInterval: TimeInterval = 6 * 60 * 60
    ) {
        self.session = session
        self.bundle = bundle
        self.userDefaults = userDefaults
        self.checkInterval = checkInterval
    }

    func checkAutomaticallyIfNeeded() {
        let now = Date()
        let lastCheck = userDefaults.object(forKey: "FlowLastReleaseUpdateCheck") as? Date
        if let lastCheck, now.timeIntervalSince(lastCheck) < checkInterval {
            return
        }
        userDefaults.set(now, forKey: "FlowLastReleaseUpdateCheck")
        checkForUpdates(userInitiated: false)
    }

    func checkForUpdates(userInitiated: Bool) {
        checkTask?.cancel()
        checkTask = Task { [weak self] in
            guard let self else { return }
            do {
                guard let update = try await self.fetchAvailableUpdate() else {
                    if userInitiated {
                        self.presentNoUpdateAlert()
                    }
                    return
                }
                self.presentUpdateAlert(update)
            } catch {
                if userInitiated {
                    self.presentUpdateFailureAlert(error)
                }
            }
        }
    }

    private func fetchAvailableUpdate() async throws -> NativeReleaseUpdate? {
        let feedURL = updateFeedURL()
        var request = URLRequest(url: feedURL)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("Flow-GTD", forHTTPHeaderField: "User-Agent")

        let (data, response) = try await session.data(for: request)
        if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode >= 400 {
            throw NativeReleaseUpdateError.badStatus(httpResponse.statusCode)
        }

        let release = try JSONDecoder().decode(NativeReleaseUpdate.self, from: data)
        let latest = NativeReleaseVersion(release.tagName)
        let current = NativeReleaseVersion(currentVersion())
        return latest.isNewer(than: current) ? release : nil
    }

    private func updateFeedURL() -> URL {
        let environment = ProcessInfo.processInfo.environment
        if let configured = environment["FLOW_UPDATE_CHECK_URL"], let url = URL(string: configured) {
            return url
        }
        if let configured = bundle.object(forInfoDictionaryKey: "FlowReleaseFeedURL") as? String,
           let url = URL(string: configured) {
            return url
        }
        return URL(string: "https://api.github.com/repos/jasonhotsauce/flow-gtd/releases/latest")!
    }

    private func currentVersion() -> String {
        bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.0.0"
    }

    private func presentUpdateAlert(_ update: NativeReleaseUpdate) {
        let alert = NSAlert()
        alert.messageText = "Flow GTD \(NativeReleaseVersion(update.tagName).rawValue) is available"
        alert.informativeText = "Install the latest Homebrew Cask update now. Flow GTD will quit while Homebrew replaces the app."
        alert.addButton(withTitle: "Install Update")
        alert.addButton(withTitle: "Later")
        if let releaseURL = update.htmlURL {
            alert.addButton(withTitle: "View Release")
            let response = alert.runModal()
            if response == .alertFirstButtonReturn {
                installWithHomebrew(targetVersion: NativeReleaseVersion(update.tagName).rawValue)
            } else if response == .alertThirdButtonReturn {
                NSWorkspace.shared.open(releaseURL)
            }
        } else if alert.runModal() == .alertFirstButtonReturn {
            installWithHomebrew(targetVersion: NativeReleaseVersion(update.tagName).rawValue)
        }
    }

    private func presentNoUpdateAlert() {
        let alert = NSAlert()
        alert.messageText = "Flow GTD is up to date"
        alert.informativeText = "Version \(currentVersion()) is the latest available release."
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }

    private func presentUpdateFailureAlert(_ error: Error) {
        let alert = NSAlert(error: error)
        alert.messageText = "Could not check for updates"
        alert.runModal()
    }

    private func installWithHomebrew(targetVersion: String) {
        guard let brewPath = findHomebrew() else {
            presentMissingHomebrewAlert()
            return
        }

        let logPath = "/tmp/flow-gtd-homebrew-update.log"
        let script = """
        exec >"\(logPath)" 2>&1
        sleep 1
        "\(brewPath)" update
        "\(brewPath)" upgrade --cask flow-gtd || "\(brewPath)" reinstall --cask flow-gtd
        osascript -e 'display notification "Flow GTD \(targetVersion) has been installed." with title "Flow GTD Update Complete"'
        open -a "Flow GTD" || true
        """

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-lc", script]

        do {
            try process.run()
            NSApp.terminate(nil)
        } catch {
            presentUpdateFailureAlert(error)
        }
    }

    private func findHomebrew() -> String? {
        let candidates = [
            "/opt/homebrew/bin/brew",
            "/usr/local/bin/brew"
        ]
        return candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) })
    }

    private func presentMissingHomebrewAlert() {
        let alert = NSAlert()
        alert.messageText = "Homebrew is required to update Flow GTD"
        alert.informativeText = "Install updates from Terminal with: brew update && brew upgrade --cask flow-gtd"
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

enum NativeReleaseUpdateError: LocalizedError {
    case badStatus(Int)

    var errorDescription: String? {
        switch self {
        case .badStatus(let statusCode):
            return "GitHub returned HTTP \(statusCode)."
        }
    }
}
