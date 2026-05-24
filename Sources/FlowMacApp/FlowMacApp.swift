import SwiftUI

enum MainWindowMetrics {
    static let defaultWidth: CGFloat = 1440
    static let defaultHeight: CGFloat = 900
    static let minimumWidth: CGFloat = 1120
    static let minimumHeight: CGFloat = 720
}

@main
struct FlowMacApp: App {
    @NSApplicationDelegateAdaptor(AppActivationDelegate.self) private var appDelegate
    @StateObject private var store: WorkspaceStore
    @StateObject private var sidecarRuntime: SidecarRuntimeModel
    @StateObject private var updateController = NativeReleaseUpdateController()

    init() {
        let context = AppBootstrap.makeContext()
        _store = StateObject(wrappedValue: context.store)
        _sidecarRuntime = StateObject(wrappedValue: context.sidecarRuntime)
    }

    var body: some Scene {
        WindowGroup("Flow GTD") {
            RootSplitView(store: store, sidecarRuntime: sidecarRuntime)
                .background(MainWindowConfigurator())
                .frame(
                    minWidth: MainWindowMetrics.minimumWidth,
                    minHeight: MainWindowMetrics.minimumHeight
                )
                .preferredColorScheme(.dark)
                .onAppear {
                    updateController.checkAutomaticallyIfNeeded()
                }
        }
        .defaultSize(
            width: MainWindowMetrics.defaultWidth,
            height: MainWindowMetrics.defaultHeight
        )
        .windowResizability(.contentMinSize)
        .commands {
            SidebarCommands()
            CommandGroup(after: .appInfo) {
                Button("Check for Updates...") {
                    updateController.checkForUpdates(userInitiated: true)
                }
            }
        }
    }
}
