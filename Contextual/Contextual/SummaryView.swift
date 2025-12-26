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
