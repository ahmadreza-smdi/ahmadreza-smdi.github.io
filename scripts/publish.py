"""Prepare and push the reviewed Pages branch. Native deployment remains a separate manual command."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_publish_tree import DISCOVERY, ROOT, allowed, build


def git(*args, **kwargs):
    return subprocess.check_output(["git", *args], cwd=ROOT, **kwargs)


def clean_main():
    if git("branch", "--show-current").strip() != b"main":
        raise ValueError("Run from the main checkout")
    staged = git("diff", "--cached", "--no-renames", "--name-only", "-z", "--").split(b"\0")
    for name in filter(None, staged):
        path = Path(os.fsdecode(name))
        if any("vault" in part.casefold() or part.casefold() in {"cv", "important-docs"} for part in path.parts):
            raise ValueError(f"Protected path staged: {path}. Unstage it before publishing.")
    if git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ValueError("Tracked or staged edits present. Commit the reviewed changes before publishing.")
    return git("rev-parse", "HEAD").strip()


def remote_head(branch):
    found = git("ls-remote", "--heads", "origin", "refs/heads/" + branch).split()
    return found[0].decode() if found else None


def tracking_site():
    ref = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/site"],
                         cwd=ROOT, capture_output=True, check=False)
    if ref.returncode not in (0, 1):
        raise ValueError("Could not read the local origin/site tracking ref")
    return ref.stdout.decode().strip() or None


def check_main():
    revision = clean_main()
    if remote_head("main") != revision.decode():
        raise ValueError("Local main differs from origin/main. Review both revisions, pull --ff-only or push reviewed changes first.")
    return revision


def deploy_command(sha):
    # Both shells live only for this manual build. The worker restores on normal
    # exit/signals; its parent restores if the worker cannot run its exit trap.
    return f"""sh -eu <<'PAGES'
R=repos/ahmadreza-smdi/ahmadreza-smdi.github.io
expected={sha}
api() {{ sleep 1.1; "${{PAGES_GH:-gh}}" api -H 'User-Agent: Website-Review/1.0' "$@"; }}
restore() {{
  for attempt in 1 2 3; do
    if api -X PUT "$R/pages" -f build_type=workflow; then return 0; fi
  done
  echo "Workflow restore failed. Run: gh api -X PUT $R/pages -f build_type=workflow" >&2
  return 1
}}
worker() {{
  finish() {{
    result=$?
    trap - EXIT
    trap '' HUP INT TERM
    restore || exit 1
    exit "$result"
  }}
  trap finish EXIT
  trap 'exit 130' HUP INT TERM
  api -X PUT "$R/pages" -f build_type=legacy -f 'source[branch]=site' -f 'source[path]=/'
  sleep 2
  api -X POST "$R/pages/builds"
  for attempt in $(seq 1 90); do
    sleep 5
    state=$(api "$R/pages/builds/latest" --jq '.status+" "+.commit')
    case "$state" in
      "built $expected") echo "Pages built $expected"; exit 0 ;;
      "errored $expected") echo "Pages build failed for $expected" >&2; exit 1 ;;
    esac
  done
  echo "Timed out waiting for Pages to build $expected" >&2
  exit 1
}}
worker & child=$!
stop() {{
  trap '' HUP INT TERM
  kill -TERM "$child" 2>/dev/null || :
  wait "$child" || :
  restore || exit 1
  echo "Deployment interrupted; Pages workflow mode restored" >&2
  exit 130
}}
trap stop HUP INT TERM
result=0
wait "$child" || result=$?
if [ "$result" -gt 128 ]; then restore || exit 1; fi
exit "$result"
PAGES"""


def entries_at(revision):
    entries = {}
    for entry in git("ls-tree", "-rz", revision).split(b"\0"):
        if entry:
            meta, name = entry.split(b"\t", 1)
            entries[os.fsdecode(name)] = meta.split()
    return entries


def live_build_commit():
    data = json.loads(subprocess.check_output([
        "gh", "api", "-H", "User-Agent: Website-Review/1.0",
        "repos/ahmadreza-smdi/ahmadreza-smdi.github.io/pages/builds/latest",
    ]))
    if data.get("status") != "built":
        raise ValueError("Initial migration requires a successful current Pages build")
    return data["commit"]


def publish(initial_live_tree=None, dry_run=False, rollback=False):
    revision = check_main()
    known_site = tracking_site()
    holds = json.loads((ROOT / "publish-extra.json").read_text(encoding="utf-8"))["release_holds"]
    if holds:
        raise ValueError("Live preservation gate has unresolved paths: " + ", ".join(holds))
    parent = remote_head("site")
    if parent != known_site:
        raise ValueError("Remote site differs from local origin/site. Fetch origin site and review its history before retrying.")
    if rollback and not parent:
        raise ValueError("Rollback requires an existing site commit with a parent.")
    if initial_live_tree and parent:
        raise ValueError("An initial migration requires a new site branch")
    if parent:
        git("fetch", "origin", "refs/heads/site")
        if git("rev-parse", "FETCH_HEAD").decode().strip() != parent:
            raise ValueError("Remote site changed during planning; review and run again")
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        output = directory / "site"
        paths = build(ROOT, output)
        index_environment = dict(os.environ, GIT_INDEX_FILE=str(directory / "index"))
        git("read-tree", "--empty", env=index_environment)
        # Object IDs must match tracked, reviewed Git bytes, including CSV line endings.
        entries = entries_at(revision)
        if parent and not rollback:
            previous_paths = set(entries_at(parent))
            lost = sorted(path for path in previous_paths - set(paths) if path in entries
                          and path.startswith("assets/") and Path(path).suffix.lower() in
                          {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".svg", ".mp4", ".webm"})
            if lost:
                raise ValueError("Previously published media would lose its direct URL. Review publish-extra.json: "
                                 + ", ".join(lost))
        live_entries = entries_at(live_build_commit()) if initial_live_tree else None
        index = bytearray()
        for path in paths:
            mode, _, oid = entries[path]
            with (output / path).open("rb") as file:
                if git("hash-object", "--stdin", stdin=file).strip() != oid:
                    raise ValueError(f"Built bytes differ from the reviewed commit: {path}")
            if live_entries is not None:
                previous = live_entries.get(path)
                if not previous or previous[0] not in {b"100644", b"100755"} or previous[1] != b"blob":
                    raise ValueError(f"Missing or non-regular path in deployed source: {path}")
                if path == ".gitattributes" and previous[2] != oid:
                    raise ValueError("Deployed .gitattributes differs from its reviewed public bytes")
                mode, _, oid = previous
            index.extend(mode + b" " + oid + b"\t" + os.fsencode(path) + b"\0")
        git("update-index", "-z", "--index-info", input=bytes(index), env=index_environment)
        tree = git("write-tree", env=index_environment).strip().decode()
        if initial_live_tree and tree != initial_live_tree:
            raise ValueError("Initial tree differs from the independent live inventory proof")
        if rollback:
            history = git("rev-list", "--parents", "-1", parent).decode().split()
            if len(history) != 2:
                raise ValueError("Rollback requires a site commit with exactly one parent.")
            previous = entries_at(history[1])
            # Never resurrect a withdrawn route or expose a path outside today's reviewed set.
            if not DISCOVERY.issubset(previous) or not previous.keys() <= set(paths):
                raise ValueError("Previous tree contains withdrawn paths or lacks required discovery files.")
            if any(not allowed(path) or mode not in {b"100644", b"100755"} or kind != b"blob"
                   for path, (mode, kind, _) in previous.items()):
                raise ValueError("Previous tree contains a protected or non-regular path.")
            if previous[".gitattributes"][2] != entries[".gitattributes"][2]:
                raise ValueError("Previous tree has unreviewed .gitattributes bytes.")
            tree = git("rev-parse", history[1] + "^{tree}").decode().strip()
        if dry_run:
            print(f"Dry run verified {len(paths)} reviewed paths. Tree: {tree}. No ref was pushed.")
            return
        if parent and git("rev-parse", parent + "^{tree}").decode().strip() == tree:
            commit = parent
        else:
            message = "Roll back site " + parent if rollback else "Publish reviewed site from " + revision.decode()
            args = ["commit-tree", tree, "-m", message]
            if parent:
                args.extend(["-p", parent])
            commit = git(*args).decode().strip()
            if check_main() != revision or remote_head("site") != parent:
                raise ValueError("Remote or source changed during the build. Review before retrying.")
            git("pull", "--ff-only")
            if clean_main() != revision or remote_head("site") != parent:
                raise ValueError("Main or site changed before the push. Review before retrying.")
            try:
                git("push", "origin", commit + ":refs/heads/site")
            except subprocess.CalledProcessError as error:
                try:
                    observed = remote_head("site")
                except subprocess.CalledProcessError:
                    raise ValueError(f"Push result unknown. Check origin/site for {commit} before retrying.") from error
                if observed != commit:
                    raise ValueError("Site push failed. No deployment was requested. Review origin/site before retrying.") from error
                git("fetch", "origin", "refs/heads/site:refs/remotes/origin/site")
                if tracking_site() != commit:
                    raise ValueError("Acknowledgement lost and site has since changed. Review origin/site.")
                print("Push acknowledgement lost. Confirmed the expected commit on origin/site.")
    print(f"Reviewed tree: {tree}\nSite commit: {commit}\nManual deployment command:\n{deploy_command(commit)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial-live-tree", metavar="VERIFIED_TREE_ID",
                        help="First migration only: preserve the deployed blobs for the reviewed paths")
    parser.add_argument("--dry-run", action="store_true", help="Build and verify without changing the site ref")
    parser.add_argument("--rollback", action="store_true", help="Republish the previous site tree in a new commit")
    args = parser.parse_args()
    if args.rollback and args.initial_live_tree:
        parser.error("--rollback cannot initialize a branch")
    try:
        publish(args.initial_live_tree, args.dry_run, args.rollback)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Publish stopped: {exc}")
