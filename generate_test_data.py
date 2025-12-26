import os
import time

# CONFIG
TEST_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Contextual_Test_Zone")

def create_file(path, content, days_ago=0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    
    # Time Travel
    past_time = time.time() - (days_ago * 86400)
    os.utime(path, (past_time, past_time))
    print(f"Created: {os.path.basename(path)} (dated {days_ago} days ago)")

def generate():
    print(f"🚧 Building Extensive Test Zone at: {TEST_DIR}")
    if os.path.exists(TEST_DIR):
        import shutil
        shutil.rmtree(TEST_DIR)
    
    # --- 1. TIME TESTS ---
    # Today (0 days)
    create_file(f"{TEST_DIR}/today_notes.txt", "Meeting notes for today.", 0)
    # Yesterday (1 day)
    create_file(f"{TEST_DIR}/daily_standup.md", "# Yesterday's Standup\n- Blockers: None", 1) 
    # Last Month (30 days)
    create_file(f"{TEST_DIR}/finance/nov_budget.csv", "Category,Amount\nServer,500", 30)
    # Last Year (400 days - likely 2024 or earlier)
    create_file(f"{TEST_DIR}/archive/legacy_2024_plan.txt", "This is the roadmap from 2024.", 400)
    
    # --- 2. TECH & FORMAT TESTS ---
    # JSON (We add the word 'JSON' in content to ensure immediate matching)
    create_file(f"{TEST_DIR}/config/settings.json", '{"theme": "dark", "type": "JSON Config"}', 2)
    # Python
    create_file(f"{TEST_DIR}/src/main.py", "import flask\nprint('Starting Python Server')", 5)
    # React/TSX
    create_file(f"{TEST_DIR}/frontend/button.tsx", "export const Button = () => <button>Click</button>;", 5)
    # SQL
    create_file(f"{TEST_DIR}/db/schema.sql", "CREATE TABLE users (id INT);", 10)
    
    # --- 3. SEMANTIC / KEYWORD TESTS ---
    # "Secret"
    create_file(f"{TEST_DIR}/docs/secret_keys.txt", "AWS_KEY = AKIA_XXXX_SECRET", 3)
    # "Invoice" (Filename test)
    create_file(f"{TEST_DIR}/billing/invoice_001.txt", "Total due: $500", 15)
    # "Budget" (Concept test)
    create_file(f"{TEST_DIR}/planning/q4_budget.md", "# Q4 Financials\nProjected cost: $10k", 10)

    print("\n✅ Extensive Data Generated!")
    print("👉 Now run this EXACT command to index:")
    print("echo '{\"method\": \"index_folder\", \"params\": {\"path\": \"" + TEST_DIR + "\"}}' | nc -U /tmp/contextual.sock")

if __name__ == "__main__":
    generate()