import Foundation

struct SearchResponse: Codable {
    let status: String
    let data: [SearchResult]?
    let message: String?
}

/// Unified row model for both files and folders.
/// Backward compatible with the old backend response that only returned {path, snippet}.
struct SearchResult: Codable, Identifiable, Hashable {
    var id: String { path }

    let path: String

    // Search-only field (FTS snippet). Optional because folder listing doesn't return it.
    let snippet: String?

    // Folder-aware fields (may be present for both file and folder)
    let kind: String?        // "file" | "folder"
    let ext: String?         // e.g. "py", "tsx" (no dot)
    let summary: String?
    let tech_stack: String?

    // Optional metadata
    let size: Int?
    let last_modified: Double?
    let creation_time: Double?

    var filename: String {
        path.split(separator: "/").last.map(String.init) ?? path
    }

    var isFolder: Bool {
        (kind?.lowercased() == "folder")
    }

    var displaySnippet: String {
        let raw = (snippet?.isEmpty == false) ? snippet! : (summary ?? "")
        return raw
            .replacingOccurrences(of: "<b>", with: "")
            .replacingOccurrences(of: "</b>", with: "")
    }
}
