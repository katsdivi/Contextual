import os
from database import insert_file, insert_folder, update_folder_aggregate, add_index_root

SUPPORTED_EXTS = {
    '.txt', '.md', '.py', '.swift', '.json',
    '.js', '.ts', '.tsx', '.jsx', '.css', '.html',
    '.sql', '.csv', '.yaml', '.yml', '.sh', '.config', '.env'
}

def scan_directory(root_path):
    print(f"🕵️‍♀️ Scanning {root_path}...")
    count = 0
    folders_seen = []

    root_path = os.path.abspath(root_path)
    add_index_root(root_path)

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        # Index folder itself
        try:
            stats = os.stat(root)
            created = getattr(stats, 'st_birthtime', stats.st_ctime)
            insert_folder(os.path.abspath(root), stats.st_mtime, created)
            folders_seen.append(os.path.abspath(root))
        except Exception as e:
            print(f"   ⚠️ Skipped folder {os.path.basename(root)}: {e}")

        # Index files
        for file in files:
            if file.startswith('.'):
                continue

            ext = os.path.splitext(file)[1].lower()
            if ext not in SUPPORTED_EXTS:
                continue

            full_path = os.path.join(root, file)
            if process_file(full_path):
                count += 1

    # Aggregate folders bottom-up
    folders_seen.sort(key=lambda p: len(p), reverse=True)
    for folder in folders_seen:
        try:
            update_folder_aggregate(folder, max_children=60)
        except Exception as e:
            print(f"   ⚠️ Folder aggregate failed for {os.path.basename(folder)}: {e}")

    return count

def process_file(path):
    try:
        stats = os.stat(path)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        created = getattr(stats, 'st_birthtime', stats.st_ctime)
        insert_file(os.path.abspath(path), content, stats.st_mtime, created, stats.st_size)
        print(f"   -> Indexed: {os.path.basename(path)}")
        return True
    except Exception as e:
        print(f"   ⚠️ Skipped {os.path.basename(path)}: {e}")
        return False
