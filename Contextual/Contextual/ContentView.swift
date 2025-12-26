import SwiftUI
import Combine
import AppKit

struct ContentView: View {
    @ObservedObject var backend = BackendClient()
    @State private var query = ""
    @State private var results: [SearchResult] = []

    // Smart Search
    @State private var isSmartSearch: Bool = false
    @State private var isThinking: Bool = false // NEW

    @State private var selectedFileForSummary: SearchResult? = nil
    let queryPublisher = PassthroughSubject<String, Never>()

    var body: some View {
        VStack(spacing: 0) {
            // Header / Search Bar
            HStack {
                // Dynamic Icon (Magnifying Glass vs Brain)
                Image(systemName: isSmartSearch ? "brain.head.profile" : "magnifyingglass")
                    .font(.title2)
                    .foregroundColor(isSmartSearch ? .purple : .gray)
                    .symbolEffect(.bounce, value: isSmartSearch)

                TextField(
                    isSmartSearch ? "Ask Natural Language (e.g. 'files made in Oct')..." : "Search files...",
                    text: $query
                )
                .textFieldStyle(PlainTextFieldStyle())
                .font(.system(size: 18))
                .onChange(of: query) { newValue in
                    queryPublisher.send(newValue)
                }

                // --- THE PULSING BRAIN (Loading Indicator) ---
                if isThinking {
                    ProgressView()
                        .scaleEffect(0.5)
                        .padding(.trailing, 8)
                }

                // Clear button
                if !query.isEmpty {
                    Button(action: {
                        query = ""
                        results = []
                    }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.gray)
                    }
                    .buttonStyle(PlainButtonStyle())
                }

                // Toggle Button
                Button(action: {
                    withAnimation { isSmartSearch.toggle() }
                    performSearch(for: query)
                }) {
                    Text(isSmartSearch ? "AI ON" : "AI OFF")
                        .font(.caption)
                        .fontWeight(.bold)
                        .padding(4)
                        .background(isSmartSearch ? Color.purple.opacity(0.1) : Color.gray.opacity(0.1))
                        .foregroundColor(isSmartSearch ? .purple : .gray)
                        .cornerRadius(4)
                }
                .buttonStyle(PlainButtonStyle())
            }
            .padding()
            .background(Color(nsColor: .windowBackgroundColor))

            Divider()

            if results.isEmpty {
                VStack {
                    Spacer()
                    if query.isEmpty {
                        VStack(spacing: 8) {
                            Text("Ready to Search")
                                .font(.title3)
                                .foregroundStyle(.secondary)

                            Text("Press ⌘⇧C to toggle Smart Search")
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                        }
                    } else {
                        Text("No results found")
                            .font(.headline)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                .frame(maxHeight: .infinity)
            } else {
                List(results) { result in
                    HStack(alignment: .top) {
                        Image(systemName: "doc.text.fill")
                            .font(.title2)
                            .foregroundColor(.blue)
                            .padding(.top, 4)

                        VStack(alignment: .leading, spacing: 6) {
                            Text(result.path.components(separatedBy: "/").last ?? result.path)
                                .font(.headline)
                                .fontWeight(.semibold)

                            Text(
                                result.snippet
                                    .replacingOccurrences(of: "<b>", with: "")
                                    .replacingOccurrences(of: "</b>", with: "")
                            )
                            .font(.system(.caption, design: .monospaced))
                            .padding(8)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.primary.opacity(0.05))
                            .cornerRadius(6)
                            .overlay(
                                RoundedRectangle(cornerRadius: 6)
                                    .stroke(Color.primary.opacity(0.1), lineWidth: 1)
                            )

                            Text(result.path)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                                .lineLimit(1)
                                .truncationMode(.middle)
                        }

                        Spacer()

                        Button(action: {
                            self.selectedFileForSummary = result
                        }) {
                            Image(systemName: "sparkles")
                                .foregroundColor(.purple)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .padding(.top, 4)
                    }
                    .padding(.vertical, 8)
                    .contentShape(Rectangle())
                    .onTapGesture(count: 2) {
                        openFile(path: result.path)
                    }
                }
                .sheet(item: $selectedFileForSummary) { file in
                    SummaryView(
                        path: file.path,
                        query: query,
                        backend: backend,
                        isPresented: Binding(
                            get: { selectedFileForSummary != nil },
                            set: { if !$0 { selectedFileForSummary = nil } }
                        )
                    )
                }
            }
        }
        .frame(minWidth: 600, minHeight: 400)

        // Keyboard Shortcut Trigger (⌘⇧C)
        .background(
            Button("Toggle AI") {
                withAnimation { isSmartSearch.toggle() }
                performSearch(for: query)
            }
            .keyboardShortcut("c", modifiers: [.command, .shift])
            .opacity(0)
        )
        .onReceive(queryPublisher.debounce(for: .milliseconds(300), scheduler: RunLoop.main)) { debouncedQuery in
            performSearch(for: debouncedQuery)
        }
    }

    func performSearch(for searchText: String) {
        let trimmed = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            self.results = []
            return
        }

        // Toggle Thinking ON if in Smart Mode
        if isSmartSearch {
            isThinking = true
        }

        print("Searching for: \(trimmed) [AI: \(isSmartSearch)]")

        backend.sendRequest(
            method: "search",
            params: ["query": trimmed, "use_ai": isSmartSearch]
        ) { response in
            // Toggle Thinking OFF when done
            DispatchQueue.main.async {
                self.isThinking = false

                if let data = response["data"] as? [[String: Any]] {
                    self.results = data.compactMap { dict in
                        guard let path = dict["path"] as? String,
                              let snippet = dict["snippet"] as? String else { return nil }
                        return SearchResult(path: path, snippet: snippet)
                    }
                } else {
                    self.results = []
                }
            }
        }
    }

    func openFile(path: String) {
        let url = URL(fileURLWithPath: path)
        NSWorkspace.shared.open(url)
    }
}
