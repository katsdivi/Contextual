import socket
import json
import time

SOCKET_PATH = "/tmp/contextual.sock"

TESTS = [
    # --- GROUP 1: DATES ---
    {"name": "Date: Today", "query": "files from today", "expect": "today_notes.txt"},
    {"name": "Date: Yesterday", "query": "files made yesterday", "expect": "daily_standup.md"},
    {"name": "Date: Year 2024", "query": "files from 2024", "expect": "legacy_2024_plan.txt"},
    
    # --- GROUP 2: FILE TYPES ---
    {"name": "Type: JSON", "query": "json files", "expect": "settings.json"},
    {"name": "Type: Python", "query": "python scripts", "expect": "main.py"},
    {"name": "Type: SQL", "query": "sql files", "expect": "schema.sql"},
    
    # --- GROUP 3: CONTENT & CONCEPTS ---
    {"name": "Content: Secret", "query": "secret keys", "expect": "secret_keys.txt"},
    {"name": "Content: Budget", "query": "budget files", "expect": "nov_budget.csv"},
    {"name": "Content: React", "query": "react components", "expect": "button.tsx"},
    
    # --- GROUP 4: FILENAMES ---
    {"name": "Filename: Invoice", "query": "invoice", "expect": "invoice_001.txt"},
    {"name": "Filename: Config", "query": "settings", "expect": "settings.json"},
    
    # --- GROUP 5: COMPLEX ---
    {"name": "Complex: Python Main", "query": "main python file", "expect": "main.py"}
]

def send_request(request):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
        client.sendall(json.dumps(request).encode('utf-8'))
        client.shutdown(socket.SHUT_WR) # Deadlock prevention
        
        response_data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk: break
            response_data += chunk
        return json.loads(response_data.decode('utf-8'))
    except Exception as e:
        return {}
    finally:
        client.close()

def run_suite():
    print(f"\n🧪 STARTING EXTENSIVE TEST SUITE ({len(TESTS)} Tests)")
    print("="*50)
    
    score = 0
    
    for i, test in enumerate(TESTS, 1):
        print(f"Test {i:02d}: {test['name']:<25} | Query: '{test['query']}'", end=" ... ")
        
        # Run Search
        req = {"method": "search", "params": {"query": test['query'], "use_ai": True}}
        res = send_request(req)
        results = res.get("data", [])
        
        # Check
        found_files = [r['path'].split('/')[-1] for r in results]
        passed = any(test['expect'] in f for f in found_files)
        
        if passed:
            print("✅ PASS")
            score += 1
        else:
            print("❌ FAIL")
            print(f"       Expected: {test['expect']}")
            print(f"       Found:    {found_files[:3]}...")

    print("="*50)
    print(f"📊 FINAL SCORE: {score}/{len(TESTS)}")
    if score == len(TESTS):
        print("🎉 CERTIFIED: ENGINE IS ROBUST.")
    else:
        print("⚠️  Needs calibration.")

if __name__ == "__main__":
    run_suite()