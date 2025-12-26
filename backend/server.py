import socket
import os
import json
import threading
import time

from database import (
    search_index,
    update_summary,
    get_summary,
    get_file_metadata,
    update_tech_stack,
    get_unsummarized_files,
    list_folder_children,
    update_folder_aggregate_up_tree,
    get_best_root_for_path,
)
from indexer import scan_directory
from ai import generate_summary, refine_summary, detect_tech_stack, analyze_search_context, parse_search_intent

SOCKET_PATH = "/tmp/contextual.sock"
BUFFER_SIZE = 4096


def handle_request(raw_data):
    try:
        request = json.loads(raw_data)
        method = request.get("method")
        params = request.get("params", {})

        print(f"received command: {method} with params: {params}")

        if method == "ping":
            return {"status": "success", "message": "pong", "data": "Python is alive!"}

        elif method == "index_folder":
            path = params.get("path")
            if not path or not os.path.exists(path):
                return {"status": "error", "message": "Invalid path"}

            count = scan_directory(path)
            return {"status": "success", "message": f"Indexed {count} files"}

        elif method == "search":
            query = params.get("query")
            use_ai = params.get("use_ai", False)

            final_query = query or ""

            if use_ai:
                print("🧠 AI Thinking (Qwen)...")
                translated_query = parse_search_intent(final_query)
                translated_query = (translated_query or "").replace("%", "*")

                if translated_query and translated_query != final_query:
                    print(f"🔍 Executing AI Query: '{translated_query}'")
                    final_query = translated_query
                else:
                    print("⚠️ AI Fallback: Using raw query")

            root_path = params.get("root_path")
            results = search_index(final_query, root_path=root_path)

            print(f"✅ Found {len(results)} matches. Top results:")
            for res in results[:5]:
                name = os.path.basename(res["path"])
                kind = res.get("kind", "file")
                icon = "📁" if kind == "folder" else "📄"
                print(f"   {icon} {name}")

            return {"status": "success", "data": results}

        elif method == "get_summary":
            path = params.get("path")

            saved_summary = get_summary(path)
            if saved_summary:
                return {"status": "success", "data": saved_summary, "source": "db"}

            if not os.path.exists(path):
                return {"status": "error", "message": "File not found"}

            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            new_summary = generate_summary(content)
            update_summary(path, new_summary)

            stop_at = get_best_root_for_path(path)
            update_folder_aggregate_up_tree(path, stop_at=stop_at)

            return {"status": "success", "data": new_summary, "source": "ai"}

        elif method == "save_summary":
            path = params.get("path")
            new_text = params.get("summary")
            update_summary(path, new_text)

            stop_at = get_best_root_for_path(path)
            update_folder_aggregate_up_tree(path, stop_at=stop_at)

            return {"status": "success", "message": "Saved"}

        elif method == "refine_summary":
            current_text = params.get("current_summary")
            instruction = params.get("instruction")
            new_text = refine_summary(current_text, instruction)
            return {"status": "success", "data": new_text}

        elif method == "get_expanded_details":
            path = params.get("path")
            query = params.get("query")

            meta = get_file_metadata(path)
            if not meta:
                return {"status": "error"}

            kind = meta.get("kind", "file")
            tech_stack = meta.get("tech_stack") or ""

            if kind == "folder":
                return {
                    "status": "success",
                    "tech_stack": tech_stack or "Mixed",
                    "search_context": "Folder result. Use list_folder to browse.",
                    "created": meta.get("creation_time"),
                    "modified": meta.get("last_modified"),
                    "kind": "folder",
                }

            if not tech_stack and os.path.exists(path):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                tech_stack = detect_tech_stack(content)
                update_tech_stack(path, tech_stack)

            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            search_context = analyze_search_context(content, query or "")

            return {
                "status": "success",
                "tech_stack": tech_stack,
                "search_context": search_context,
                "created": meta.get("creation_time"),
                "modified": meta.get("last_modified"),
                "kind": "file",
            }

        elif method == "list_folder":
            folder_path = params.get("path")
            if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                return {"status": "error", "message": "Folder not found"}

            children = list_folder_children(folder_path)
            return {"status": "success", "data": children}

        else:
            return {"status": "error", "message": "Unknown method"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def background_summarizer():
    print("🧠 AI Worker: Started. Watching for new files...")

    while True:
        try:
            files_to_do = get_unsummarized_files()
            if not files_to_do:
                time.sleep(5)
                continue

            path = files_to_do[0]
            print(f"🧠 AI Worker: Analyzing {os.path.basename(path)}...")

            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                summary = generate_summary(content)
                update_summary(path, summary)

                stop_at = get_best_root_for_path(path)
                update_folder_aggregate_up_tree(path, stop_at=stop_at)

            time.sleep(0.5)

        except Exception as e:
            print(f"⚠️ AI Worker Error: {e}")
            time.sleep(5)


def start_server():
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
        except OSError:
            pass

    worker = threading.Thread(target=background_summarizer, daemon=True)
    worker.start()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(1)

    print(f"🚀 Contextual Backend listening on {SOCKET_PATH}...")

    try:
        while True:
            connection, _ = server.accept()
            try:
                while True:
                    data = connection.recv(BUFFER_SIZE)
                    if not data:
                        break
                    response = handle_request(data.decode('utf-8'))
                    connection.sendall(json.dumps(response).encode('utf-8'))
            finally:
                connection.close()

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


if __name__ == "__main__":
    start_server()
