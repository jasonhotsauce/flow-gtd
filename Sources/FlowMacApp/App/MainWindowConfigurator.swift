import AppKit
import SwiftUI

struct MainWindowConfigurator: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let view = NSView(frame: .zero)
        configureWindow(from: view)
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        configureWindow(from: nsView)
    }

    private func configureWindow(from view: NSView) {
        DispatchQueue.main.async {
            guard let window = view.window else {
                return
            }
            window.isMovableByWindowBackground = true
        }
    }
}
