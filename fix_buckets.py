#!/usr/bin/env python3
"""
fix_buckets.py — Fix bucket files for Ombre Brain

Scans buckets_dir for files that the BucketManager can't load:
  1. JSON files → converts to frontmatter .md
  2. .md files without frontmatter → wraps with proper YAML frontmatter
  3. Files in type dirs but not in domain subdirs → moves to 未分类/
  4. Files in the root buckets/ dir → moves to dynamic/未分类/

Run on the VPS:
  cd /opt/ombre-brain
  python fix_buckets.py [--buckets-dir ./buckets] [--dry-run]
"""

import os
import sys
import json
import uuid
import shutil
import argparse
from datetime import datetime
from pathlib import Path

try:
    import frontmatter
except ImportError:
    print("Error: python-frontmatter not installed. Run: pip install python-frontmatter")
    sys.exit(1)


def generate_id():
    return uuid.uuid4().hex[:12]


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sanitize_name(name):
    if not name:
        return ""
    name = name.strip()
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '_')
    return name[:80]


def json_to_md(data, source_file):
    """Convert a JSON bucket object to frontmatter Post."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None

    # Extract content
    content = data.get("content", "")
    if not content:
        # Try nested structures
        content = data.get("text", data.get("body", data.get("summary", "")))
    if not content:
        # Maybe the whole thing is metadata-only
        return None

    # Extract or generate metadata
    bucket_id = data.get("id", data.get("bucket_id", generate_id()))
    name = data.get("name", data.get("title", ""))
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    domain = data.get("domain", data.get("domains", ["未分类"]))
    if isinstance(domain, str):
        domain = [domain]
    if not domain:
        domain = ["未分类"]

    metadata = {
        "id": str(bucket_id),
        "name": sanitize_name(name) or str(bucket_id),
        "tags": tags,
        "domain": domain,
        "valence": float(data.get("valence", 0.5)),
        "arousal": float(data.get("arousal", 0.3)),
        "importance": int(data.get("importance", 5)),
        "type": data.get("type", "dynamic"),
        "created": data.get("created", data.get("created_at", data.get("timestamp", now_iso()))),
        "last_active": data.get("last_active", data.get("updated_at", now_iso())),
        "activation_count": int(data.get("activation_count", 0)),
        "resolved": data.get("resolved", False),
        "pinned": data.get("pinned", False),
    }

    return frontmatter.Post(content, **metadata)


def fix_md_file(filepath):
    """Check if .md file has valid frontmatter; fix if not."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    # Try parsing as frontmatter
    try:
        post = frontmatter.loads(raw)
        if post.metadata and "id" in post.metadata:
            return post, False  # Already valid
    except Exception:
        pass

    # No valid frontmatter — wrap the raw content
    bucket_id = generate_id()
    stem = Path(filepath).stem
    metadata = {
        "id": bucket_id,
        "name": sanitize_name(stem) or bucket_id,
        "tags": [],
        "domain": ["未分类"],
        "valence": 0.5,
        "arousal": 0.3,
        "importance": 5,
        "type": "dynamic",
        "created": now_iso(),
        "last_active": now_iso(),
        "activation_count": 0,
    }
    post = frontmatter.Post(raw.strip(), **metadata)
    return post, True  # Was fixed


def determine_type_dir(post, base_dir):
    """Determine the correct type directory for a bucket."""
    btype = post.metadata.get("type", "dynamic")
    if btype == "permanent" or post.metadata.get("pinned"):
        return os.path.join(base_dir, "permanent")
    elif btype == "feel":
        return os.path.join(base_dir, "feel")
    elif btype in ("archived", "archive"):
        return os.path.join(base_dir, "archive")
    else:
        return os.path.join(base_dir, "dynamic")


def process_file(filepath, base_dir, dry_run=False):
    """Process a single file, returning (action, detail) tuple."""
    ext = Path(filepath).suffix.lower()

    if ext == ".json":
        # JSON file → convert to .md
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return "SKIP", f"invalid JSON: {e}"

        # Handle arrays of buckets
        if isinstance(data, list):
            results = []
            for i, item in enumerate(data):
                post = json_to_md(item, filepath)
                if post:
                    results.append((post, f"item[{i}]"))
            if not results:
                return "SKIP", "no convertible items in array"
            for post, label in results:
                _write_bucket(post, base_dir, dry_run)
            if not dry_run:
                os.remove(filepath)
            return "CONVERTED", f"JSON array → {len(results)} .md files"
        else:
            post = json_to_md(data, filepath)
            if not post:
                return "SKIP", "no content found in JSON"
            _write_bucket(post, base_dir, dry_run)
            if not dry_run:
                os.remove(filepath)
            return "CONVERTED", "JSON → .md"

    elif ext == ".md":
        post, was_fixed = fix_md_file(filepath)
        if was_fixed:
            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(frontmatter.dumps(post))
            # Check if it needs to move to a domain subdir
            _ensure_domain_subdir(filepath, post, base_dir, dry_run)
            return "FIXED", "added frontmatter"
        else:
            # Valid .md — but check if it's in the right place
            moved = _ensure_domain_subdir(filepath, post, base_dir, dry_run)
            if moved:
                return "MOVED", f"→ domain subdir"
            return "OK", "valid"
    else:
        return "SKIP", f"unsupported extension: {ext}"


def _write_bucket(post, base_dir, dry_run):
    """Write a Post to the correct directory."""
    type_dir = determine_type_dir(post, base_dir)
    domain = post.metadata.get("domain", ["未分类"])
    if post.metadata.get("type") == "feel":
        primary_domain = "沉淀物"
    else:
        primary_domain = sanitize_name(domain[0]) if domain else "未分类"
    target_dir = os.path.join(type_dir, primary_domain)

    bucket_id = post.metadata.get("id", generate_id())
    name = post.metadata.get("name", "")
    if name and name != bucket_id:
        filename = f"{sanitize_name(name)}_{bucket_id}.md"
    else:
        filename = f"{bucket_id}.md"

    if not dry_run:
        os.makedirs(target_dir, exist_ok=True)
        outpath = os.path.join(target_dir, filename)
        with open(outpath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))


def _ensure_domain_subdir(filepath, post, base_dir, dry_run):
    """If file is directly in a type dir (not in a domain subdir), move it."""
    parent = os.path.dirname(filepath)
    parent_name = os.path.basename(parent)

    # Check if parent is one of the type directories directly
    type_dirs = {"permanent", "dynamic", "archive", "feel"}
    if parent_name in type_dirs:
        # File is directly in type dir, needs domain subdir
        domain = post.metadata.get("domain", ["未分类"])
        if post.metadata.get("type") == "feel":
            primary_domain = "沉淀物"
        else:
            primary_domain = sanitize_name(domain[0]) if domain else "未分类"
        target_dir = os.path.join(parent, primary_domain)
        if not dry_run:
            os.makedirs(target_dir, exist_ok=True)
            dest = os.path.join(target_dir, os.path.basename(filepath))
            if not os.path.exists(dest):
                shutil.move(filepath, dest)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Fix Ombre Brain bucket files")
    parser.add_argument("--buckets-dir", default="./buckets",
                        help="Path to buckets directory (default: ./buckets)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.buckets_dir)
    if not os.path.exists(base_dir):
        print(f"Error: {base_dir} does not exist")
        sys.exit(1)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Scanning: {base_dir}")
    print("=" * 60)

    stats = {"OK": 0, "FIXED": 0, "CONVERTED": 0, "MOVED": 0, "SKIP": 0}

    # Walk all files in the buckets directory tree
    for root, dirs, files in os.walk(base_dir):
        for fname in sorted(files):
            filepath = os.path.join(root, fname)
            rel = os.path.relpath(filepath, base_dir)
            action, detail = process_file(filepath, base_dir, args.dry_run)
            stats[action] = stats.get(action, 0) + 1
            icon = {"OK": "✓", "FIXED": "🔧", "CONVERTED": "🔄", "MOVED": "📦", "SKIP": "⏭️"}.get(action, "?")
            if action != "OK":
                print(f"  {icon} [{action}] {rel}: {detail}")

    # Also check for files directly in base_dir (root level)
    for fname in os.listdir(base_dir):
        fpath = os.path.join(base_dir, fname)
        if os.path.isfile(fpath):
            ext = Path(fpath).suffix.lower()
            if ext in (".md", ".json"):
                print(f"  📦 [ROOT] {fname}: moving to dynamic/")
                if ext == ".json":
                    action, detail = process_file(fpath, base_dir, args.dry_run)
                    print(f"       → {action}: {detail}")
                else:
                    post, was_fixed = fix_md_file(fpath)
                    if was_fixed and not args.dry_run:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(frontmatter.dumps(post))
                    _write_bucket(post, base_dir, args.dry_run)
                    if not args.dry_run:
                        os.remove(fpath)
                stats["MOVED"] = stats.get("MOVED", 0) + 1

    print("=" * 60)
    print(f"Results: {stats}")
    if args.dry_run:
        print("\nThis was a dry run. Re-run without --dry-run to apply changes.")
    else:
        print("\nDone! Restart Ombre Brain: sudo systemctl restart ombre-brain")


if __name__ == "__main__":
    main()
