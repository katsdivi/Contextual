import sqlite3
import os
import datetime
import re
from collections import Counter

DB_PATH = "contextual.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Registry: files and folders
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        path TEXT PRIMARY KEY,
        kind TEXT,          -- "file" or "folder"
        ext TEXT,           -- file extension without dot, empty for folders
        last_modified REAL,
        creation_time REAL,
        size INTEGER,
        indexed_at REAL,
        summary TEXT,
        tech_stack TEXT
    )
    ''')

    # Roots table: used to limit aggregate updates to the indexed root folder
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS index_roots (
        root_path TEXT PRIMARY KEY,
        indexed_at REAL
    )
    ''')

    # Migrations for older DBs
    try:
        cursor.execute("ALTER TABLE files ADD COLUMN kind TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE files ADD COLUMN ext TEXT")
    except Exception:
        pass

    cursor.execute("UPDATE files SET kind = 'file' WHERE kind IS NULL OR kind = ''")

    # FTS index: path is indexed, includes kind+ext
    cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS file_index USING fts5(
        path,
        kind,
        ext,
        content,
        summary,
        tech_stack,
        created_str,
        modified_str,
        tokenize='porter'
    )
    ''')

    conn.commit()
    conn.close()


# -------------------------
# Roots tracking
# -------------------------

def add_index_root(root_path: str):
    rp = os.path.abspath(root_path)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO index_roots (root_path, indexed_at) VALUES (?, ?)', (rp, datetime.datetime.now().timestamp()))
    conn.commit()
    conn.close()


def get_best_root_for_path(path: str):
    """
    Returns the longest matching indexed root that prefixes the given path.
    """
    p = os.path.abspath(path)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT root_path FROM index_roots')
    roots = [r["root_path"] for r in cursor.fetchall()]
    conn.close()

    best = None
    for r in roots:
        r2 = os.path.abspath(r)
        if p == r2 or p.startswith(r2.rstrip(os.sep) + os.sep):
            if best is None or len(r2) > len(best):
                best = r2
    return best


# -------------------------
# Insert and update records
# -------------------------

def insert_file(path, content, last_modified, creation_time, size):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT summary, tech_stack FROM files WHERE path = ?', (path,))
        row = cursor.fetchone()
        summary = row['summary'] if row else None
        tech_stack = row['tech_stack'] if row else None

        ext = os.path.splitext(path)[1].lower().lstrip(".")
        kind = "file"

        cursor.execute('''
        INSERT OR REPLACE INTO files (path, kind, ext, last_modified, creation_time, size, indexed_at, summary, tech_stack)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
        ''', (path, kind, ext, last_modified, creation_time, size, summary, tech_stack))

        c_str = datetime.datetime.fromtimestamp(creation_time).strftime('%Y %b %d %A')
        m_str = datetime.datetime.fromtimestamp(last_modified).strftime('%Y %b %d %A')

        cursor.execute('DELETE FROM file_index WHERE path = ?', (path,))
        cursor.execute('''
        INSERT INTO file_index (path, kind, ext, content, summary, tech_stack, created_str, modified_str)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (path, kind, ext, content, summary or "", tech_stack or "", c_str, m_str))

        conn.commit()
        return True
    except Exception as e:
        print(f"❌ DB Error (insert_file): {e}")
        return False
    finally:
        conn.close()


def insert_folder(path, last_modified, creation_time):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        kind = "folder"
        ext = ""

        cursor.execute('SELECT summary, tech_stack FROM files WHERE path = ?', (path,))
        row = cursor.fetchone()
        summary = row['summary'] if row else None
        tech_stack = row['tech_stack'] if row else None

        cursor.execute('''
        INSERT OR REPLACE INTO files (path, kind, ext, last_modified, creation_time, size, indexed_at, summary, tech_stack)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
        ''', (path, kind, ext, last_modified, creation_time, 0, summary, tech_stack))

        c_str = datetime.datetime.fromtimestamp(creation_time).strftime('%Y %b %d %A')
        m_str = datetime.datetime.fromtimestamp(last_modified).strftime('%Y %b %d %A')

        cursor.execute('DELETE FROM file_index WHERE path = ?', (path,))
        cursor.execute('''
        INSERT INTO file_index (path, kind, ext, content, summary, tech_stack, created_str, modified_str)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (path, kind, ext, "", summary or "", tech_stack or "", c_str, m_str))

        conn.commit()
        return True
    except Exception as e:
        print(f"❌ DB Error (insert_folder): {e}")
        return False
    finally:
        conn.close()


def update_tech_stack(path, new_stack):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE files SET tech_stack = ? WHERE path = ?', (new_stack, path))
    conn.commit()
    conn.close()


def get_file_metadata(path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT last_modified, creation_time, tech_stack, kind, ext FROM files WHERE path = ?', (path,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_summary(path, new_summary):
    """
    Updates registry summary and keeps FTS row consistent.
    Works for both files and folders.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('UPDATE files SET summary = ? WHERE path = ?', (new_summary, path))

    cursor.execute('SELECT kind, ext, content, tech_stack, created_str, modified_str FROM file_index WHERE path = ?', (path,))
    row = cursor.fetchone()

    if row:
        cursor.execute('DELETE FROM file_index WHERE path = ?', (path,))
        cursor.execute('''
        INSERT INTO file_index (path, kind, ext, content, summary, tech_stack, created_str, modified_str)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (path, row['kind'], row['ext'], row['content'], new_summary, row['tech_stack'], row['created_str'], row['modified_str']))
    else:
        meta = get_file_metadata(path) or {}
        kind = meta.get("kind", "file")
        ext = meta.get("ext", "")
        cursor.execute('''
        INSERT INTO file_index (path, kind, ext, content, summary, tech_stack, created_str, modified_str)
        VALUES (?, ?, ?, ?, ?, "", "", "")
        ''', (path, kind, ext, "", new_summary))

    conn.commit()
    conn.close()
    print(f"✅ Saved summary for {os.path.basename(path)}")


def get_summary(path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT summary FROM files WHERE path = ?', (path,))
    row = cursor.fetchone()
    conn.close()
    return row['summary'] if row else None


# -------------------------
# Folder aggregation
# -------------------------

def _infer_stack_from_ext(ext_counts: Counter):
    mapping = {
        "py": "Python",
        "js": "JavaScript",
        "ts": "TypeScript",
        "tsx": "React, TypeScript",
        "jsx": "React, JavaScript",
        "sql": "SQL",
        "json": "JSON",
        "md": "Markdown",
        "csv": "CSV",
        "yml": "YAML",
        "yaml": "YAML",
        "swift": "Swift",
        "html": "HTML",
        "css": "CSS",
        "sh": "Shell",
        "env": "Env",
        "config": "Config",
    }

    labels = []
    for ext, _cnt in ext_counts.most_common(12):
        if not ext:
            continue
        lbl = mapping.get(ext.lower())
        labels.append(lbl if lbl else ext.upper())

    seen = set()
    out = []
    for x in labels:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _fetch_children_rows(folder_path: str, recursive: bool):
    base = folder_path.rstrip(os.sep) + os.sep
    conn = get_db_connection()
    cursor = conn.cursor()

    if recursive:
        cursor.execute('''
        SELECT path, kind, ext, summary
        FROM files
        WHERE path LIKE ?
          AND path != ?
        ''', (base + "%", folder_path))
        rows = cursor.fetchall()
        conn.close()
        return rows

    # direct only
    cursor.execute('''
    SELECT path, kind, ext, summary
    FROM files
    WHERE path LIKE ?
      AND path != ?
    ''', (base + "%", folder_path))
    rows = cursor.fetchall()
    conn.close()

    out = []
    for r in rows:
        p = r["path"]
        rel = p[len(base):]
        if not rel:
            continue
        if os.sep in rel:
            continue
        out.append(r)
    return out


def _compute_folder_stats(rows, max_children: int):
    file_count = 0
    folder_count = 0
    ext_counts = Counter()
    filenames = []
    summary_bits = []

    for r in rows:
        p = r["path"]
        k = r["kind"]
        e = r["ext"] or ""
        s = (r["summary"] or "").strip()

        name = os.path.basename(p)
        filenames.append(name)

        if k == "folder":
            folder_count += 1
        else:
            file_count += 1
            ext_counts[e] += 1

        if s:
            summary_bits.append(f"{name}: {s}")

    inferred = _infer_stack_from_ext(ext_counts)
    tech_stack = ", ".join(inferred) if inferred else "Mixed"

    top_ext = ", ".join([f"{k}:{v}" for k, v in ext_counts.most_common(5) if k])
    if top_ext:
        summary = f"Folder with {file_count} files and {folder_count} subfolders. Top types: {top_ext}."
    else:
        summary = f"Folder with {file_count} files and {folder_count} subfolders."

    limited_names = " ".join(filenames[:max_children])
    limited_summaries = " ".join(summary_bits[:max_children])
    content = f"{summary} {limited_names} {limited_summaries}".strip()

    return summary, tech_stack, content


def update_folder_aggregate(folder_path, max_children=60):
    """
    Enhancement:
    - files table gets DIRECT-CHILD aggregates (good for open folder)
    - FTS gets RECURSIVE aggregates (good for search)
    """
    folder_path = os.path.abspath(folder_path)

    direct_rows = _fetch_children_rows(folder_path, recursive=False)
    rec_rows = _fetch_children_rows(folder_path, recursive=True)

    direct_summary, direct_stack, _direct_content = _compute_folder_stats(direct_rows, max_children=max_children)
    rec_summary, rec_stack, rec_content = _compute_folder_stats(rec_rows, max_children=max_children)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update registry with DIRECT aggregates
    cursor.execute('UPDATE files SET summary = ?, tech_stack = ? WHERE path = ?', (direct_summary, direct_stack, folder_path))

    # Preserve created/modified strings
    cursor.execute('SELECT created_str, modified_str FROM file_index WHERE path = ?', (folder_path,))
    meta = cursor.fetchone()
    created_str = meta["created_str"] if meta else ""
    modified_str = meta["modified_str"] if meta else ""

    # Update FTS with RECURSIVE aggregates
    cursor.execute('DELETE FROM file_index WHERE path = ?', (folder_path,))
    cursor.execute('''
    INSERT INTO file_index (path, kind, ext, content, summary, tech_stack, created_str, modified_str)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (folder_path, "folder", "", rec_content, rec_summary, rec_stack, created_str, modified_str))

    conn.commit()
    conn.close()


def update_folder_aggregate_up_tree(path, stop_at=None):
    """
    Enhancement:
    Stops at the indexed root folder, never walks up to '/'.
    """
    p = os.path.abspath(path)
    stop = os.path.abspath(stop_at) if stop_at else None

    current = p if os.path.isdir(p) else os.path.dirname(p)

    while current and current != os.path.dirname(current):
        meta = get_file_metadata(current)
        if meta and meta.get("kind") == "folder":
            try:
                update_folder_aggregate(current, max_children=60)
            except Exception as e:
                print(f"⚠️ Folder aggregate error for {current}: {e}")

        if stop and os.path.abspath(current) == stop:
            break

        current = os.path.dirname(current)


# -------------------------
# Search
# -------------------------

def _get_parent_folders_for_paths(paths):
    """
    Given file paths, return existing folder records (paths) up the tree,
    stopping at the best indexed root for each path.
    """
    folder_paths = set()

    conn = get_db_connection()
    cursor = conn.cursor()

    for p in paths:
        p_abs = os.path.abspath(p)
        stop_at = get_best_root_for_path(p_abs)
        stop_at_abs = os.path.abspath(stop_at) if stop_at else None

        cur = os.path.dirname(p_abs)
        while cur and cur != os.path.dirname(cur):
            # stop_at behavior
            if stop_at_abs and cur == stop_at_abs:
                # include the root folder itself if it exists as a folder in DB
                cursor.execute("SELECT path FROM files WHERE path = ? AND kind = 'folder'", (cur,))
                if cursor.fetchone():
                    folder_paths.add(cur)
                break

            cursor.execute("SELECT path FROM files WHERE path = ? AND kind = 'folder'", (cur,))
            if cursor.fetchone():
                folder_paths.add(cur)

            cur = os.path.dirname(cur)

    conn.close()
    return sorted(folder_paths, key=lambda x: len(x))


def search_index(query, root_path=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    results = []

    if ":" in query or " AND " in query or " OR " in query:
        try:
            path_tokens = re.findall(r'path:([A-Za-z0-9_\-\.]+)\*?', query)
            for tok in path_tokens:
                cursor.execute('''
                SELECT path,
                       kind,
                       snippet(file_index, 3, '<b>', '</b>', '...', 30) as snippet
                FROM file_index
                WHERE path LIKE ?
                LIMIT 10
                ''', (f"%{tok}%",))
                results.extend([dict(row) for row in cursor.fetchall()])

            cursor.execute('''
            SELECT
              path,
              kind,
              snippet(file_index, 3, '<b>', '</b>', '...', 30) as snippet,
              bm25(file_index, 6.0, 2.0, 1.0, 2.0, 1.0, 0.4, 0.4, 0.4) as score
            FROM file_index
            WHERE file_index MATCH ?
            ORDER BY score
            LIMIT 20
            ''', (query,))
            results.extend([dict(row) for row in cursor.fetchall()])
        except Exception as e:
            print(f"⚠️ SQL Match Error: {e}")

    else:
        q = query.strip().lower()

        ext_alias = {
            "sql files": "sql",
            "sql file": "sql",
            "csv files": "csv",
            "csv file": "csv",
            "json files": "json",
            "json file": "json",
            "python scripts": "py",
            "python script": "py",
            "react components": "tsx",
            "react component": "tsx",
        }

        if q in ext_alias:
            e = ext_alias[q]
            cursor.execute('''
            SELECT path, kind, snippet(file_index, 3, '<b>', '</b>', '...', 30) as snippet
            FROM file_index
            WHERE ext = ?
            LIMIT 20
            ''', (e,))
            results.extend([dict(row) for row in cursor.fetchall()])

        cursor.execute('''
        SELECT path, kind, snippet(file_index, 3, '<b>', '</b>', '...', 30) as snippet
        FROM file_index
        WHERE path LIKE ?
        LIMIT 10
        ''', (f"%{query}%",))
        results.extend([dict(row) for row in cursor.fetchall()])

        try:
            cursor.execute('''
            SELECT path, kind, snippet(file_index, 3, '<b>', '</b>', '...', 30) as snippet
            FROM file_index
            WHERE file_index MATCH ?
            LIMIT 20
            ''', (query,))
            results.extend([dict(row) for row in cursor.fetchall()])
        except Exception:
            pass

    conn.close()

        # Deduplicate
    unique_results = []
    seen = set()
    for res in results:
        if res['path'] not in seen:
            unique_results.append(res)
            seen.add(res['path'])

    # ----------------------------
    # Folder bubbling enhancement:
    # If files match, also return parent folders up to indexed root.
    # This makes queries like "AKIA" return folders too.
    # ----------------------------

        # Optional root scoping
    if root_path:
        root_abs = os.path.abspath(root_path).rstrip(os.sep) + os.sep
        unique_results = [
            r for r in unique_results
            if os.path.abspath(r["path"]) == os.path.abspath(root_path)
            or os.path.abspath(r["path"]).startswith(root_abs)
        ]
        seen = set(r["path"] for r in unique_results)

    file_paths = [r["path"] for r in unique_results if r.get("kind") == "file"]
    if file_paths:
        parent_folders = _get_parent_folders_for_paths(file_paths)

        # Append folder entries if not already present
        for fp in parent_folders:
            if fp in seen:
                continue
            unique_results.append({
                "path": fp,
                "kind": "folder",
                "snippet": "Contains matching files."
            })
            seen.add(fp)

    return unique_results[:20]



# -------------------------
# Folder listing
# -------------------------

def list_folder_children(folder_path):
    base = os.path.abspath(folder_path).rstrip(os.sep) + os.sep
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT path, kind, ext, last_modified, creation_time, size, summary, tech_stack FROM files WHERE path LIKE ?', (base + "%",))
    rows = cursor.fetchall()
    conn.close()

    out = []
    for r in rows:
        p = r["path"]
        rel = p[len(base):]
        if not rel:
            continue
        if os.sep in rel:
            continue
        out.append(dict(r))

    out.sort(key=lambda x: (0 if x["kind"] == "folder" else 1, os.path.basename(x["path"]).lower()))
    return out


def get_unsummarized_files():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM files WHERE kind='file' AND (summary IS NULL OR summary = '')")
    rows = cursor.fetchall()
    conn.close()
    return [row['path'] for row in rows]


def rebuild_fts_index():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('DROP TABLE IF EXISTS file_index')

    cursor.execute('''
    CREATE VIRTUAL TABLE file_index USING fts5(
        path,
        kind,
        ext,
        content,
        summary,
        tech_stack,
        created_str,
        modified_str,
        tokenize='porter'
    )
    ''')
    conn.commit()

    cursor.execute('SELECT path, kind, ext, last_modified, creation_time, summary, tech_stack FROM files')
    rows = cursor.fetchall()

    for r in rows:
        path = r["path"]
        kind = r["kind"] or "file"
        ext = r["ext"] or ""
        content = ""

        if kind == "file":
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                content = ""

        c_str = datetime.datetime.fromtimestamp(r["creation_time"]).strftime('%Y %b %d %A')
        m_str = datetime.datetime.fromtimestamp(r["last_modified"]).strftime('%Y %b %d %A')

        cursor.execute('''
        INSERT INTO file_index (path, kind, ext, content, summary, tech_stack, created_str, modified_str)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (path, kind, ext, content, r["summary"] or "", r["tech_stack"] or "", c_str, m_str))

    conn.commit()
    conn.close()
    print("✅ Rebuilt FTS index.")


init_db()
