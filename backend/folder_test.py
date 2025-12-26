import socket
import json
import os

SOCKET_PATH = "/tmp/contextual.sock"

# Folder test zone path (matches your generator)
FOLDER_TEST_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Contextual_Folder_Test_Zone")

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
    {"name": "Complex: Python Main", "query": "main python file", "expect": "main.py"},
]


def send_request(request):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(SOCKET_PATH)
        client.sendall(json.dumps(request).encode("utf-8"))
        client.shutdown(socket.SHUT_WR)

        response_data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response_data += chunk

        if not response_data:
            return {}

        return json.loads(response_data.decode("utf-8"))
    except Exception:
        return {}
    finally:
        client.close()


def _basename(p: str) -> str:
    return p.split("/")[-1]


def _print_fail(expected, found):
    print("❌ FAIL")
    print(f"       Expected: {expected}")
    print(f"       Found:    {found}")


def run_search_suite():
    print(f"\n🧪 STARTING EXTENSIVE TEST SUITE ({len(TESTS)} Tests)")
    print("=" * 50)

    score = 0

    for i, test in enumerate(TESTS, 1):
        print(f"Test {i:02d}: {test['name']:<25} | Query: '{test['query']}'", end=" ... ")

        req = {"method": "search", "params": {"query": test["query"], "use_ai": True}}
        res = send_request(req)
        results = res.get("data", [])

        found_files = [_basename(r.get("path", "")) for r in results]
        passed = any(test["expect"] in f for f in found_files)

        if passed:
            print("✅ PASS")
            score += 1
        else:
            _print_fail(test["expect"], f"{found_files[:5]}...")

    print("=" * 50)
    print(f"📊 FINAL SCORE: {score}/{len(TESTS)}")
    if score == len(TESTS):
        print("🎉 CERTIFIED: ENGINE IS ROBUST.")
        return True
    else:
        print("⚠️  Needs calibration.")
        return False


def run_folder_suite():
    """
    Folder tests assume you already indexed ~/Documents/Contextual_Folder_Test_Zone
    created by the folder generator.
    """
    print("\n🧪 STARTING FOLDER TEST SUITE (4 Tests)")
    print("=" * 50)

    score = 0
    total = 4

    root = FOLDER_TEST_DIR
    finance = os.path.join(root, "finance")
    frontend = os.path.join(root, "frontend")

    # Test F1: Search should return folder due to recursive folder indexing
    print("Test F1: Folder Search (recursive)     | Query: 'nov_budget'", end=" ... ")
    req = {"method": "search", "params": {"query": "nov_budget", "use_ai": False}}
    res = send_request(req)
    results = res.get("data", [])
    paths = [r.get("path", "") for r in results]
    kinds = {r.get("path", ""): r.get("kind", "") for r in results}

    ok_file = any(p.endswith("nov_budget.csv") for p in paths)
    ok_folder = any(p == finance and kinds.get(p) == "folder" for p in paths)

    if ok_file and ok_folder:
        print("✅ PASS")
        score += 1
    else:
        _print_fail("nov_budget.csv + finance folder", f"{[(kinds.get(p,''), _basename(p)) for p in paths[:8]]}...")

    # Test F2: list_folder(root) should show direct children only
    print("Test F2: list_folder(root) direct      | Path: root", end=" ... ")
    req = {"method": "list_folder", "params": {"path": root}}
    res = send_request(req)
    children = res.get("data", [])

    names = [_basename(c.get("path", "")) for c in children]
    # Expected direct: finance, frontend, root_note.md
    ok = ("finance" in names) and ("frontend" in names) and ("root_note.md" in names) and ("nov_budget.csv" not in names)

    if ok:
        print("✅ PASS")
        score += 1
    else:
        _print_fail("finance, frontend, root_note.md only", names)

    # Test F3: list_folder(finance) should not leak nested deep/secrets.txt
    print("Test F3: list_folder(finance) direct   | Path: finance", end=" ... ")
    req = {"method": "list_folder", "params": {"path": finance}}
    res = send_request(req)
    children = res.get("data", [])
    names = [_basename(c.get("path", "")) for c in children]

    ok = ("nov_budget.csv" in names) and ("schema.sql" in names) and ("deep" in names) and ("secrets.txt" not in names)

    if ok:
        print("✅ PASS")
        score += 1
    else:
        _print_fail("nov_budget.csv, schema.sql, deep (no secrets.txt)", names)

    # Test F4: Folder entries should have folder properties (summary + tech_stack)
    print("Test F4: Folder properties present     | Path: frontend", end=" ... ")
    req = {"method": "list_folder", "params": {"path": root}}
    res = send_request(req)
    children = res.get("data", [])

    # find frontend folder row
    frontend_row = None
    for c in children:
        if c.get("path", "") == frontend and c.get("kind") == "folder":
            frontend_row = c
            break

    if frontend_row and frontend_row.get("summary") and frontend_row.get("tech_stack"):
        print("✅ PASS")
        score += 1
    else:
        _print_fail("frontend folder has summary + tech_stack", frontend_row)

    print("=" * 50)
    print(f"📊 FOLDER SCORE: {score}/{total}")
    if score == total:
        print("🎉 FOLDERS: VERIFIED.")
        return True
    else:
        print("⚠️  Folders need calibration.")
        return False


if __name__ == "__main__":
    ok_search = run_search_suite()
    ok_folders = run_folder_suite()

    if ok_search and ok_folders:
        print("\n✅ ALL TEST SUITES PASSED.")
    else:
        print("\n❌ SOME TESTS FAILED.")
