//
//  SummaryView.swift
//  Contextual
//
//  Updated on 12/19/25
//

import SwiftUI

struct SummaryView: View {
    var path: String
    var query: String
    @ObservedObject var backend: BackendClient
    @Binding var isPresented: Bool
    
    @State private var summaryText: String = "Loading..."
    @State private var aiInstruction: String = ""
    
    // Expanded states
    @State private var isExpanded: Bool = false
    @State private var techStack: String = "Loading..."
    @State private var searchContext: String = "Analyzing..."
    
    // Folder details (optional)
    @State private var folderStatsLine: String = ""
    @State private var folderTypesLine: String = ""
    @State private var folderReactLine: String = ""
    @State private var folderReactFiles: [String] = []
    @State private var createdDate: String = ""
    @State private var modifiedDate: String = ""
    
    var body: some View {
        ZStack(alignment: .bottomLeading) {
            
            VStack(alignment: .leading, spacing: 12) {
                
                // Header
                HStack {
                    Image(systemName: "doc.text.fill")
                        .foregroundColor(.blue)
                    
                    Text(path.components(separatedBy: "/").last ?? "File")
                        .font(.headline)
                    
                    Spacer()
                    
                    Button("Done") {
                        isPresented = false
                    }
                }
                
                // Summary Editor
                TextEditor(text: $summaryText)
                    .font(.body)
                    .padding(6)
                    .background(Color.primary.opacity(0.05))
                    .cornerRadius(8)
                    .frame(minHeight: 100)
                
                // AI Refine Bar
                HStack {
                    TextField("Ask AI to change summary...", text: $aiInstruction)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                    
                    Button(action: refineWithAI) {
                        Image(systemName: "wand.and.stars")
                    }
                    .disabled(aiInstruction.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                
                Divider()
                
                // Expansion Zone
                if isExpanded {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 10) {
                            
                            // Search Context
                            Group {
                                Text("🔍 Usage of '\(query)'")
                                    .font(.caption)
                                    .bold()
                                    .foregroundColor(.secondary)
                                
                                TextEditor(text: $searchContext)
                                    .font(.body)
                                    .padding(6)
                                    .frame(height: 60)
                                    .background(Color.primary.opacity(0.05))
                                    .cornerRadius(6)
                                    .disabled(true)
                            }
                            
    
                        // Folder Details (if backend returned them)
                        if !folderStatsLine.isEmpty || !folderTypesLine.isEmpty || !folderReactLine.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                HStack(spacing: 8) {
                                    Image(systemName: "folder.fill")
                                        .foregroundColor(.orange)
                                    Text("Folder Details")
                                        .font(.caption)
                                        .bold()
                                        .foregroundColor(.secondary)
                                }

                                if !folderStatsLine.isEmpty {
                                    Text(folderStatsLine)
                                        .font(.callout)
                                }

                                if !folderTypesLine.isEmpty {
                                    Text(folderTypesLine)
                                        .font(.callout)
                                        .foregroundColor(.secondary)
                                }

                                if !folderReactLine.isEmpty {
                                    Text(folderReactLine)
                                        .font(.callout)
                                }

                                if !folderReactFiles.isEmpty {
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("React files")
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                        ForEach(folderReactFiles.prefix(12), id: \.self) { f in
                                            Text("• " + f)
                                                .font(.caption)
                                        }
                                        if folderReactFiles.count > 12 {
                                            Text("… and \(folderReactFiles.count - 12) more")
                                                .font(.caption2)
                                                .foregroundColor(.secondary)
                                        }
                                    }
                                }
                            }
                            .padding()
                            .background(Color.secondary.opacity(0.15))
                            .cornerRadius(12)
                        }

                        // Tech Stack
                            Group {
                                Text("🛠️ Tech Stack")
                                    .font(.caption)
                                    .bold()
                                    .foregroundColor(.secondary)
                                
                                TextField("Stack", text: $techStack)
                                    .textFieldStyle(RoundedBorderTextFieldStyle())
                                    .disabled(true)
                            }
                            
                            // Metadata
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Created")
                                        .font(.caption2)
                                        .foregroundColor(.gray)
                                    Text(createdDate.isEmpty ? "—" : createdDate)
                                        .font(.caption)
                                }
                                
                                Spacer()
                                
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Modified")
                                        .font(.caption2)
                                        .foregroundColor(.gray)
                                    Text(modifiedDate.isEmpty ? "—" : modifiedDate)
                                        .font(.caption)
                                }
                            }
                        }
                        .padding(4)
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }
                
                Spacer()
                
                // Footer Save Button
                HStack {
                    Spacer()
                    Button("Save All") {
                        saveChanges()
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            .padding()
            
            // Floating Expand Button
            // ... inside ZStack ...
                        
                        // --- THE FLOATING EXPAND BUTTON ---
                        Button(action: {
                            withAnimation(.spring(response: 0.5, dampingFraction: 0.7)) {
                                isExpanded.toggle()
                                if isExpanded { loadExtendedDetails() }
                            }
                        }) {
                            ZStack {
                                Circle()
                                    .fill(Color(red: 0.2, green: 0.8, blue: 0.2)) // Brighter "Hacker Green"
                                    .frame(width: 44, height: 44) // Slightly larger to match screenshot
                                    .shadow(radius: 4, y: 2)
                                
                                // The icon that matches your screenshot
                                Image(systemName: isExpanded ? "arrow.down.forward.and.arrow.up.backward" : "arrow.up.backward.and.arrow.down.forward")
                                    .font(.system(size: 20, weight: .bold))
                                    .foregroundColor(.white)
                            }
                        }
                        .buttonStyle(PlainButtonStyle())
                        .padding(.bottom, 20)
                        .padding(.leading, 20)
        }
        // Fluid window resizing
        .frame(
            width: isExpanded ? 700 : 500,
            height: isExpanded ? 650 : 400
        )
        .onAppear(perform: loadSummary)
    }
    
    // MARK: - Backend Calls
    
    func loadSummary() {
        backend.sendRequest(method: "get_summary", params: ["path": path]) { response in
            if let text = response["data"] as? String {
                self.summaryText = text
            }
        }
    }
    
    func refineWithAI() {
        let trimmed = aiInstruction.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        
        let params: [String: Any] = [
            "current_summary": summaryText,
            "instruction": trimmed
        ]
        
        backend.sendRequest(method: "refine_summary", params: params) { response in
            if let newText = response["data"] as? String {
                self.summaryText = newText
                self.aiInstruction = ""
            }
        }
    }
    
    func loadExtendedDetails() {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        
        backend.sendRequest(
            method: "get_expanded_details",
            params: ["path": path, "query": query]
        ) { response in
            if let stack = response["tech_stack"] as? String {
                self.techStack = stack
            }
            
            // UI safety: if backend guessed poorly, infer from extension
            if (self.techStack.lowercased() == "markdown" || self.techStack.lowercased() == "plain text" || self.techStack.lowercased() == "unknown"),
               let inferred = inferredTechFromExtension(path: path) {
                self.techStack = inferred
            }

            if let details = response["folder_details"] as? [String: Any] {
                if let stats = details["stats_line"] as? String { self.folderStatsLine = stats }
                if let types = details["types_line"] as? String { self.folderTypesLine = types }
                if let reactLine = details["react_line"] as? String { self.folderReactLine = reactLine }
                if let reactFiles = details["react_files"] as? [String] { self.folderReactFiles = reactFiles }
            }
            
            if let context = response["search_context"] as? String {
                self.searchContext = context
            }
            
            if let cTime = response["created"] as? Double {
                self.createdDate = formatter.string(from: Date(timeIntervalSince1970: cTime))
            }
            
            if let mTime = response["modified"] as? Double {
                self.modifiedDate = formatter.string(from: Date(timeIntervalSince1970: mTime))
            }
        }
    }
    
    func saveChanges() {
        backend.sendRequest(
            method: "save_summary",
            params: ["path": path, "summary": summaryText]
        ) { _ in
            isPresented = false
        }
    }
}
// Infer tech stack by file extension (basic heuristic)
private func inferredTechFromExtension(path: String) -> String? {
    let ext = URL(fileURLWithPath: path).pathExtension.lowercased()
    switch ext {
    case "swift": return "Swift"
    case "m", "mm", "h": return "Objective-C/C++"
    case "js": return "JavaScript"
    case "ts": return "TypeScript"
    case "jsx": return "React (JSX)"
    case "tsx": return "React (TSX)"
    case "py": return "Python"
    case "java": return "Java"
    case "kt": return "Kotlin"
    case "cpp", "cc", "cxx": return "C++"
    case "c": return "C"
    case "rb": return "Ruby"
    case "go": return "Go"
    case "rs": return "Rust"
    case "php": return "PHP"
    case "html": return "HTML"
    case "css": return "CSS"
    case "sh": return "Shell Script"
    case "md": return "Markdown"
    default: return nil
    }
}

