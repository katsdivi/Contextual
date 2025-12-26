import Foundation

struct SearchResponse: Codable {
    let status: String
    let data: [SearchResult]?
    let message: String?
}

struct SearchResult: Codable, Identifiable {
    var id: String { path }
    let path: String
    let snippet: String
}
