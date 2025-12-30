//
//  BackendClient.swift
//  Contextual
//
//  Created by Divyam Kataria on 12/18/25.
//

import Foundation
import Network
import Combine
import SwiftUI

class BackendClient: ObservableObject {
    private var connection: NWConnection?
    private let queue = DispatchQueue(label: "com.contextual.backend")
    
    // This must match the path in server.py
    private let socketPath = "/tmp/contextual.sock"

    init() {
        connect()
    }

    func connect() {
        let endpoint = NWEndpoint.unix(path: socketPath)
        let parameters = NWParameters.tcp
        
        // Create the connection
        connection = NWConnection(to: endpoint, using: parameters)
        
        // Listen for state changes (Debugging)
        connection?.stateUpdateHandler = { state in
            switch state {
            case .ready:
                print("✅ Swift: Connected to Python Backend")
            case .failed(let error):
                print("❌ Swift: Connection failed: \(error)")
            case .waiting(let error):
                print("⚠️ Swift: Waiting for connection: \(error)")
            default:
                break
            }
        }
        
        // Start the connection
        connection?.start(queue: queue)
    }

    func sendPing() {
        let jsonString = """
        {"method": "ping", "params": {}}
        """
        
        guard let data = jsonString.data(using: .utf8) else { return }
        
        // Send Data
        connection?.send(content: data, completion: .contentProcessed { error in
            if let error = error {
                print("Error sending: \(error)")
                return
            }
            print("📤 Swift: Ping sent")
            
            // Immediately listen for a response
            self.receiveResponse()
        })
    }
    
    private func receiveResponse() {
        connection?.receive(minimumIncompleteLength: 1, maximumLength: 4096) { data, _, isComplete, error in
            if let data = data, let response = String(data: data, encoding: .utf8) {
                print("📥 Swift received: \(response)")
            }
            if let error = error {
                print("Error receiving: \(error)")
            }
        }
    }
    
    // Add this inside class BackendClient
        func search(query: String, completion: @escaping ([SearchResult]) -> Void) {
            let jsonString = """
            {"method": "search", "params": {"query": "\(query)"}}
            """
            
            guard let data = jsonString.data(using: .utf8) else { return }
            
            connection?.send(content: data, completion: .contentProcessed { error in
                if let error = error { print("Error: \(error)"); return }
                
                self.connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, _, _ in
                    if let data = data {
                        if let response = try? JSONDecoder().decode(SearchResponse.self, from: data) {
                            DispatchQueue.main.async { completion(response.data ?? []) }
                        }
                    }
                }
            })
        }
    
    // Add inside BackendClient class
        func summarize(path: String, completion: @escaping (String) -> Void) {
            let jsonString = """
            {"method": "summarize_file", "params": {"path": "\(path)"}}
            """
            
            guard let data = jsonString.data(using: .utf8) else { return }
            
            connection?.send(content: data, completion: .contentProcessed { error in
                if let error = error { print("Error: \(error)"); return }
                
                self.connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, _, _ in
                    if let data = data {
                        // Quick & dirty JSON parsing for the string response
                        if let response = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let summary = response["data"] as? String {
                            DispatchQueue.main.async { completion(summary) }
                        }
                    }
                }
            })
        }
    
    // Add this generic helper to BackendClient class
        func sendRequest(method: String, params: [String: Any], completion: @escaping ([String: Any]) -> Void) {
            // Construct JSON
            var request: [String: Any] = ["method": method, "params": params]
            
            guard let data = try? JSONSerialization.data(withJSONObject: request) else { return }
            
            connection?.send(content: data, completion: .contentProcessed { error in
                if let error = error { print("Send Error: \(error)"); return }
                
                self.connection?.receive(minimumIncompleteLength: 1, maximumLength: 65536) { data, _, _, _ in
                    if let data = data,
                       let response = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        DispatchQueue.main.async {
                            completion(response)
                        }
                    }
                }
            })
        }


    // MARK: - High-level helpers (folders)

    func listFolder(path: String, completion: @escaping ([SearchResult]) -> Void) {
        sendRequest(method: "list_folder", params: ["path": path]) { response in
            if let data = response["data"] as? [[String: Any]] {
                let rows: [SearchResult] = data.compactMap { dict in
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
                completion(rows)
            } else {
                completion([])
            }
        }
    }

}
