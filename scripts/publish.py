"""Prepare and push the reviewed Pages branch. Native deployment remains a separate manual command."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_publish_tree import ROOT, build


def git(*args, **kwargs):
    return subprocess.check_output(["git", *args], cwd=ROOT, **kwargs)


def clean_main():
    if git("branch", "--show-current").strip() != b"main":
        raise ValueError("Run from the main checkout")
    git("diff", "--quiet", "HEAD", "--")
    return git("rev-parse", "HEAD").strip()


def deploy_command(sha):
    return f"""sh -eu <<'PAGES'
R=repos/ahmadreza-smdi/ahmadreza-smdi.github.io
expected={sha}
api() {{ gh api -H 'User-Agent: Website-Review/1.0' "$@"; }}
restore() {{ api -X PUT "$R/pages" -f build_type=workflow; }}
trap 'restore' EXIT
trap 'exit 1' HUP INT TERM
api -X PUT "$R/pages" -f build_type=legacy -f 'source[branch]=site' -f 'source[path]=/'
sleep 2
api -X POST "$R/pages/builds"
for attempt in $(seq 1 90); do
  sleep 5
  state=$(api "$R/pages/builds/latest" --jq '.status+" "+.commit')
  case "$state" in
    "built $expected") exit 0 ;;
    "errored $expected") exit 1 ;;
  esac
done
exit 1
PAGES"""


def publish():
    clean_main()
    git("pull", "--ff-only")
    revision = clean_main()
    holds = json.loads((ROOT / "publish-extra.json").read_text(encoding="utf-8"))["release_holds"]
    if holds:
        raise ValueError("Live preservation gate has unresolved paths: " + ", ".join(holds))
    upstream = git("rev-parse", "@{upstream}").strip()
    if upstream != revision:
        raise ValueError("Push the reviewed main commit before publishing its tree")
    remote = git("ls-remote", "--heads", "origin", "refs/heads/site").split()
    parent = remote[0].decode() if remote else None
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
        entries = {}
        for entry in git("ls-tree", "-rz", "HEAD").split(b"\0"):
            if entry:
                meta, name = entry.split(b"\t", 1)
                entries[os.fsdecode(name)] = meta.split()
        index = bytearray()
        for path in paths:
            mode, _, oid = entries[path]
            with (output / path).open("rb") as file:
                if git("hash-object", "--stdin", stdin=file).strip() != oid:
                    raise ValueError(f"Built bytes differ from the reviewed commit: {path}")
            index.extend(mode + b" " + oid + b"\t" + os.fsencode(path) + b"\0")
        git("update-index", "-z", "--index-info", input=bytes(index), env=index_environment)
        tree = git("write-tree", env=index_environment).strip().decode()
        if parent and git("rev-parse", parent + "^{tree}").decode().strip() == tree:
            commit = parent
        else:
            args = ["commit-tree", tree, "-m", "Publish reviewed site from " + revision.decode()]
            if parent:
                args.extend(["-p", parent])
            commit = git(*args).decode().strip()
            git("pull", "--ff-only")
            if clean_main() != revision:
                raise ValueError("Main changed during the build; review and run again")
            git("push", "origin", commit + ":refs/heads/site")
    print(f"Reviewed tree: {tree}\nSite commit: {commit}\nManual deployment command:\n{deploy_command(commit)}")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        publish()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Publish stopped: {exc}")

