import SwiftUI
import Combine
import AppKit

private enum ExplorerMode: Equatable {
    case search
    case browse(path: String)
}

struct ContentView: View {
    @ObservedObject var backend = BackendClient()

    @State private var query = ""
    @State private var results: [SearchResult] = []

    // Browse mode
    @State private var mode: ExplorerMode = .search
    @State private var browsePath: String? = nil
    @State private var browseRows: [SearchResult] = []

    // Smart Search
    @State private var isSmartSearch: Bool = false
    @State private var isThinking: Bool = false

    @State private var selectedItemForSummary: SearchResult? = nil

    let queryPublisher = PassthroughSubject<String, Never>()

    var body: some View {
        VStack(spacing: 0) {
            headerBar

            Divider()

            if displayRows.isEmpty {
                emptyState
            } else {
                List {
                    if !folderRows.isEmpty {
                        Section(header: Text("Folders").foregroundStyle(.secondary)) {
                            ForEach(folderRows) { row in
                                ResultRow(
                                    row: row,
                                    query: query,
                                    onOpen: { openFile(path: row.path) },
                                    onBrowse: { openFolder(path: row.path) },
                                    onSummarize: { selectedItemForSummary = row }
                                )
                            }
                        }
                    }

                    if !fileRows.isEmpty {
                        Section(header: Text("Files").foregroundStyle(.secondary)) {
                            ForEach(fileRows) { row in
                                ResultRow(
                                    row: row,
                                    query: query,
                                    onOpen: { openFile(path: row.path) },
                                    onBrowse: { openFolder(path: row.path) },
                                    onSummarize: { selectedItemForSummary = row }
                                )
                            }
                        }
                    }
                }
                .listStyle(.inset)
                .sheet(item: $selectedItemForSummary) { item in
                    SummaryView(
                        path: item.path,
                        query: query,
                        backend: backend,
                        isPresented: Binding(
                            get: { selectedItemForSummary != nil },
                            set: { if !$0 { selectedItemForSummary = nil } }
                        )
                    )
                }
            }
        }
        .frame(minWidth: 720, minHeight: 480)
        .background(Color(nsColor: .windowBackgroundColor))

        // Keyboard Shortcut Trigger (⌘⇧C)
        .background(
            Button("Toggle AI") {
                withAnimation { isSmartSearch.toggle() }
                triggerQueryAction()
            }
            .keyboardShortcut("c", modifiers: [.command, .shift])
            .opacity(0)
        )
        .onReceive(queryPublisher.debounce(for: .milliseconds(250), scheduler: RunLoop.main)) { _ in
            // If user is browsing, we keep list_folder view when query is empty.
            // If they type something, we search globally (consistent mental model).
            triggerQueryAction()
        }
        .onAppear {
            // If you want a default browse root later, call openFolder(path: "...") here.
        }
    }

    // MARK: - Derived UI

    private var displayRows: [SearchResult] {
        // Folder-heavy queries should surface folders first.
        let q = query.lowercased()
        let folderIntent = q.contains("folder") || q.contains("folders") || q.contains("directory") || q.contains("directories")

        let rows: [SearchResult]
        switch mode {
        case .search:
            rows = results
        case .browse:
            if query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                rows = browseRows
            } else {
                rows = results
            }
        }

        if folderIntent {
            // Stable: folder-first, then filename
            return rows.sorted { a, b in
                if a.isFolder != b.isFolder { return a.isFolder && !b.isFolder }
                return a.filename.localizedCaseInsensitiveCompare(b.filename) == .orderedAscending
            }
        }

        return rows
    }

    private var folderRows: [SearchResult] { displayRows.filter { $0.isFolder } }
    private var fileRows: [SearchResult] { displayRows.filter { !$0.isFolder } }

    private var headerBar: some View {
        VStack(spacing: 8) {
            if case .browse(let p) = mode {
                breadcrumbsBar(for: p)
                    .padding(.horizontal)
            }

            HStack {
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

                if isThinking {
                    ProgressView()
                        .scaleEffect(0.6)
                        .padding(.trailing, 8)
                }

                if !query.isEmpty {
                    Button {
                        query = ""
                        results = []
                        // When clearing, return to browse listing if we are browsing.
                        if case .browse = mode {
                            // Keep browseRows on screen
                        } else {
                            browseRows = []
                        }
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.gray)
                    }
                    .buttonStyle(.plain)
                }

                Button {
                    withAnimation { isSmartSearch.toggle() }
                    triggerQueryAction()
                } label: {
                    Text(isSmartSearch ? "AI ON" : "AI OFF")
                        .font(.caption)
                        .fontWeight(.bold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 5)
                        .background(isSmartSearch ? Color.purple.opacity(0.12) : Color.gray.opacity(0.12))
                        .foregroundColor(isSmartSearch ? .purple : .secondary)
                        .cornerRadius(6)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal)
            .padding(.bottom, 6)
        }
        .padding(.top, 10)
    }

    private var emptyState: some View {
        VStack {
            Spacer()

            if query.isEmpty {
                VStack(spacing: 10) {
                    switch mode {
                    case .search:
                        Text("Ready to Search")
                            .font(.title3)
                            .foregroundStyle(.secondary)

                        Text("Press ⌘⇧C to toggle Smart Search")
                            .font(.caption)
                            .foregroundStyle(.tertiary)

                    case .browse:
                        Text("This folder is empty")
                            .font(.title3)
                            .foregroundStyle(.secondary)

                        Text("Type to search globally, or browse subfolders.")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                }
            } else {
                Text("No results found")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - Actions

    private func triggerQueryAction() {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)

        // In browse mode with empty query, show direct children
        if case .browse(let p) = mode, trimmed.isEmpty {
            listFolder(path: p)
            return
        }

        // Otherwise, do global search
        guard !trimmed.isEmpty else {
            results = []
            return
        }
        performSearch(for: trimmed)
    }

    private func performSearch(for searchText: String) {
        if isSmartSearch { isThinking = true }

        backend.sendRequest(
            method: "search",
            params: ["query": searchText, "use_ai": isSmartSearch]
        ) { response in
            DispatchQueue.main.async {
                self.isThinking = false

                if let data = response["data"] as? [[String: Any]] {
                    self.results = data.compactMap { dict in
                        guard let p = dict["path"] as? String else { return nil }
                        return SearchResult(
                            path: p,
                            snippet: dict["snippet"] as? String,
                            kind: dict["kind"] as? String,
                            ext: dict["ext"] as? String,
                            summary: dict["summary"] as? String,
                            tech_stack: dict["tech_stack"] as? String,
                            size: dict["size"] as? Int,
                            last_modified: dict["last_modified"] as? Double,
                            creation_time: dict["creation_time"] as? Double
                        )
                    }
                } else {
                    self.results = []
                }
            }
        }
    }

    private func listFolder(path: String) {
        backend.sendRequest(method: "list_folder", params: ["path": path]) { response in
            if let data = response["data"] as? [[String: Any]] {
                let rows = data.compactMap { dict -> SearchResult? in
                    guard let p = dict["path"] as? String else { return nil }
                    return SearchResult(
                        path: p,
                        snippet: dict["snippet"] as? String,
                        kind: dict["kind"] as? String,
                        ext: dict["ext"] as? String,
                        summary: dict["summary"] as? String,
                        tech_stack: dict["tech_stack"] as? String,
                        size: dict["size"] as? Int,
                        last_modified: dict["last_modified"] as? Double,
                        creation_time: dict["creation_time"] as? Double
                    )
                }
                DispatchQueue.main.async {
                    self.browseRows = rows
                }
            } else {
                DispatchQueue.main.async {
                    self.browseRows = []
                }
            }
        }
    }

    private func openFolder(path: String) {
        browsePath = path
        withAnimation(.easeInOut(duration: 0.15)) {
            mode = .browse(path: path)
        }
        // Reset search results so "empty query" shows folder listing
        results = []
        listFolder(path: path)
    }

    private func openFile(path: String) {
        let url = URL(fileURLWithPath: path)
        NSWorkspace.shared.open(url)
    }

    // MARK: - Breadcrumbs

    @ViewBuilder
    private func breadcrumbsBar(for path: String) -> some View {
        let comps = path.split(separator: "/").map(String.init)

        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        mode = .search
                        browsePath = nil
                        browseRows = []
                        results = []
                        query = ""
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "magnifyingglass")
                        Text("Search")
                    }
                    .font(.caption)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)

                Text("›")
                    .foregroundStyle(.tertiary)

                ForEach(Array(comps.enumerated()), id: \.offset) { idx, c in
                    let subpath = "/" + comps.prefix(idx + 1).joined(separator: "/")
                    Button {
                        openFolder(path: subpath)
                    } label: {
                        Text(c)
                            .font(.caption)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.primary.opacity(0.06))
                            .cornerRadius(6)
                    }
                    .buttonStyle(.plain)

                    if idx != comps.count - 1 {
                        Text("›").foregroundStyle(.tertiary)
                    }
                }
            }
        }
    }
}

// MARK: - Row UI

private struct ResultRow: View {
    let row: SearchResult
    let query: String
    let onOpen: () -> Void
    let onBrowse: () -> Void
    let onSummarize: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: row.isFolder ? "folder.fill" : "doc.text.fill")
                .font(.title3)
                .foregroundColor(row.isFolder ? .orange : .blue)
                .padding(.top, 4)

            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    Text(row.filename)
                        .font(.headline)
                        .fontWeight(.semibold)
                        .lineLimit(1)

                    if row.isFolder {
                        Text("Folder")
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.orange.opacity(0.12))
                            .foregroundColor(.orange)
                            .cornerRadius(6)
                    } else if let ext = row.ext, !ext.isEmpty {
                        Text(ext.uppercased())
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.blue.opacity(0.12))
                            .foregroundColor(.blue)
                            .cornerRadius(6)
                    }
                }

                if let stack = row.tech_stack, !stack.isEmpty {
                    Text(stack)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                let snippet = row.displaySnippet
                if !snippet.isEmpty {
                    Text(snippet)
                        .font(.system(.caption, design: .monospaced))
                        .padding(8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.primary.opacity(0.05))
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.primary.opacity(0.10), lineWidth: 1)
                        )
                }

                Text(row.path)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            Spacer()

            if row.isFolder {
                Button {
                    onBrowse()
                } label: {
                    Image(systemName: "chevron.right")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .padding(.top, 4)
            }

            Button {
                onSummarize()
            } label: {
                Image(systemName: "sparkles")
                    .foregroundColor(.purple)
            }
            .buttonStyle(.plain)
            .padding(.top, 4)
        }
        .padding(.vertical, 8)
        .contentShape(Rectangle())
        .onTapGesture(count: 2) {
            if row.isFolder {
                onBrowse()
            } else {
                onOpen()
            }
        }
        .contextMenu {
            Button(row.isFolder ? "Open Folder" : "Open File") {
                if row.isFolder { onBrowse() } else { onOpen() }
            }
            Button("Inspect Summary") { onSummarize() }
            Divider()
            Button("Copy Path") {
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(row.path, forType: .string)
            }
        }
    }
}
