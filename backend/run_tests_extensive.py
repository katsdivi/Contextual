import socket
import json
import os
import time
from collections import defaultdict

SOCKET_PATH = "/tmp/contextual.sock"

TEST_ZONE = os.path.join(os.path.expanduser("~"), "Documents", "Contextual_Test_Zone")
FOLDER_ZONE = os.path.join(os.path.expanduser("~"), "Documents", "Contextual_Folder_Test_Zone")

ROOTS = [TEST_ZONE, FOLDER_ZONE]


def send_request(request, timeout=3.0):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
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


def search(query, use_ai=True):
    req = {"method": "search", "params": {"query": query, "use_ai": use_ai}}
    res = send_request(req)
    return res.get("data", [])


def list_folder(path):
    req = {"method": "list_folder", "params": {"path": path}}
    res = send_request(req)
    return res.get("data", [])


def basename(p):
    return p.split("/")[-1]


def only_under_root(paths, root):
    root = os.path.abspath(root)
    root_prefix = root.rstrip(os.sep) + os.sep
    return [p for p in paths if os.path.abspath(p) == root or os.path.abspath(p).startswith(root_prefix)]


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def assert_contains(items, wanted, msg):
    if wanted not in items:
        raise AssertionError(f"{msg}\nWanted: {wanted}\nGot: {items[:12]}{'...' if len(items)>12 else ''}")


def assert_not_contains(items, unwanted, msg):
    if unwanted in items:
        raise AssertionError(f"{msg}\nUnwanted: {unwanted}\nGot: {items[:12]}{'...' if len(items)>12 else ''}")


def print_ok(name):
    print(f"✅ {name}")


def print_fail(name, e):
    print(f"❌ {name}")
    print(f"   {e}")


def run_test(name, fn):
    try:
        fn()
        print_ok(name)
        return True
    except Exception as e:
        print_fail(name, e)
        return False


def main():
    print("\n🧪 EXTENSIVE BACKEND TEST SUITE (Search + Folders + Roots + Ranking)")
    print("=" * 70)

    score = 0
    total = 0

    # Sanity: server reachable
    total += 1
    score += run_test("Server ping", lambda: assert_true(
        send_request({"method": "ping", "params": {}}).get("status") == "success",
        "Ping failed. Is backend/server.py running?"
    ))

    # Ensure both roots exist locally
    total += 1
    score += run_test("Roots exist on disk", lambda: (
        assert_true(os.path.exists(TEST_ZONE), f"Missing {TEST_ZONE}"),
        assert_true(os.path.exists(FOLDER_ZONE), f"Missing {FOLDER_ZONE}")
    ) and True)

    # ----------------------------
    # Group A: Deterministic ext queries without AI
    # ----------------------------
    total += 1
    score += run_test("Ext deterministic: sql files (no AI)", lambda: (
        assert_contains([basename(r["path"]) for r in search("sql files", use_ai=False)], "schema.sql", "Expected schema.sql")
    ) and True)

    total += 1
    score += run_test("Ext deterministic: json files (no AI)", lambda: (
        assert_contains([basename(r["path"]) for r in search("json files", use_ai=False)], "settings.json", "Expected settings.json")
    ) and True)

    # ----------------------------
    # Group B: AI date intent correctness
    # ----------------------------
    total += 1
    score += run_test("AI date: files from 2024 returns legacy_2024_plan.txt", lambda: (
        assert_contains([basename(r["path"]) for r in search("files from 2024", use_ai=True)], "legacy_2024_plan.txt", "Expected legacy_2024_plan.txt")
    ) and True)

    # ----------------------------
    # Group C: Ranking sanity: exact filename should beat folders
    # We don't have explicit ranks in response, so we enforce it appears in top N.
    # ----------------------------
    total += 1
    score += run_test("Ranking: invoice_001.txt appears in top 3 for 'invoice'", lambda: (
        assert_true(
            "invoice_001.txt" in [basename(r["path"]) for r in search("invoice", use_ai=True)[:3]],
            "Expected invoice_001.txt in top 3 results"
        )
    ) and True)

    # ----------------------------
    # Group D: Multi-root noise checks (both roots indexed)
    # We validate that folder search returns folders too, but that file is present.
    # ----------------------------
    total += 1
    score += run_test("Multi-root: react components includes button.tsx", lambda: (
        assert_contains([basename(r["path"]) for r in search("react components", use_ai=True)], "button.tsx", "Expected button.tsx")
    ) and True)

    # ----------------------------
    # Group E: Folder behavior
    # ----------------------------
    total += 1
    score += run_test("Folder list: root folder direct children only", lambda: (
        (lambda children: (
            assert_contains(children, "finance", "Missing finance in root"),
            assert_contains(children, "frontend", "Missing frontend in root"),
            assert_contains(children, "root_note.md", "Missing root_note.md in root"),
            assert_not_contains(children, "nov_budget.csv", "nov_budget.csv should not be direct child of root")
        ))([basename(x["path"]) for x in list_folder(FOLDER_ZONE)])
    ) and True)

    total += 1
    score += run_test("Folder list: finance shows deep but not secrets.txt directly", lambda: (
        (lambda children: (
            assert_contains(children, "nov_budget.csv", "Missing nov_budget.csv in finance direct children"),
            assert_contains(children, "schema.sql", "Missing schema.sql in finance direct children"),
            assert_contains(children, "deep", "Missing deep folder in finance direct children"),
            assert_not_contains(children, "secrets.txt", "secrets.txt should not be direct child of finance")
        ))([basename(x["path"]) for x in list_folder(os.path.join(FOLDER_ZONE, "finance"))])
    ) and True)

    total += 1
    score += run_test("Folder properties: folder row has summary + tech_stack", lambda: (
        (lambda rows: (
            assert_true(rows is not None, "folder not found"),
            assert_true(bool(rows.get("summary")), "folder summary missing"),
            assert_true(bool(rows.get("tech_stack")), "folder tech_stack missing"),
            True
        ))(
            next((r for r in list_folder(FOLDER_ZONE) if r.get("kind") == "folder" and r["path"].endswith("/frontend")), None)
        )
    ) and True)

    # Folder recursive search: searching secrets should show deep and finance folders
    total += 1
    score += run_test("Folder search recursive: 'AKIA' or 'SECRET' bubbles folders", lambda: (
        (lambda paths_kinds: (
            assert_true(any(k == "file" and basename(p) in ("secrets.txt", "secret_keys.txt") for p, k in paths_kinds), "Expected a secrets file"),
            assert_true(any(k == "folder" and basename(p) in ("deep", "docs", "finance") for p, k in paths_kinds), "Expected a related folder (deep/docs/finance)"),
            True
        ))([(r["path"], r.get("kind", "")) for r in search("AKIA", use_ai=False)])
    ) and True)

    # ----------------------------
    # Group F: Duplicate suppression sanity
    # Ensure no duplicate identical paths returned for a search
    # ----------------------------
    total += 1
    score += run_test("Dedup: no duplicate paths in results", lambda: (
        (lambda paths: (
            assert_true(len(paths) == len(set(paths)), f"Duplicates found: {len(paths)} returned, {len(set(paths))} unique"),
            True
        ))([r["path"] for r in search("schema.sql", use_ai=False)])
    ) and True)

    # ----------------------------
    # Group G: Stress repeated query (should be fast and stable)
    # Not timing-based, just ensure same results repeated.
    # ----------------------------
    total += 1
    def repeat_stability():
        r1 = [x["path"] for x in search("react components", use_ai=True)]
        r2 = [x["path"] for x in search("react components", use_ai=True)]
        assert_true(r1 == r2, "Results changed between identical queries")
    score += run_test("Stability: repeated query returns same paths", repeat_stability)

    # ----------------------------
    # Group H: Root containment checks for list_folder
    # ----------------------------
    total += 1
    score += run_test("List folder: all children paths remain under requested root", lambda: (
        (lambda rows: (
            assert_true(all(os.path.abspath(r["path"]).startswith(os.path.abspath(FOLDER_ZONE).rstrip(os.sep) + os.sep) for r in rows),
                        "Found child path outside root"),
            True
        ))(list_folder(FOLDER_ZONE))
    ) and True)

    print("=" * 70)
    print(f"📊 FINAL SCORE: {score}/{total}")
    if score == total:
        print("🎉 EXTENSIVE SUITE: ALL PASSED.")
    else:
        print("⚠️ EXTENSIVE SUITE: SOME FAILURES.")


if __name__ == "__main__":
    main()
