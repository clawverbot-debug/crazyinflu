#!/usr/bin/env python3
"""Create (or revoke) an API key for a collaborator. Run it yourself:
    python3 collab_key.py add alice        -> prints Alice's key (send it to her privately) and updates Netlify
    python3 collab_key.py remove alice     -> revokes her key
    python3 collab_key.py list
Keys are stored in ~/.config/viral-spy/collab_keys.json (chmod 600) and pushed to the Netlify env var API_KEYS."""
import json, os, secrets, subprocess, sys
F = os.path.expanduser("~/.config/viral-spy/collab_keys.json")
keys = json.load(open(F)) if os.path.exists(F) else {}
cmd, name = (sys.argv[1:] + ["list", ""])[:2]
name = name.strip().lower()
if cmd == "add":
    if not name or not name.replace("-", "").replace("_", "").isalnum() or len(name) > 30: sys.exit("usage: collab_key.py add <name> (letters, digits, - or _)")
    keys[name] = "ck_" + secrets.token_urlsafe(32)
elif cmd == "remove":
    keys.pop(name, None)
elif cmd != "list":
    sys.exit(__doc__)
json.dump(keys, open(F, "w"), indent=1); os.chmod(F, 0o600)
if cmd in ("add", "remove"):
    r = subprocess.run(["netlify", "env:set", "API_KEYS", json.dumps(keys), "--site", "character-lab-research"], cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard"), capture_output=True, text=True)
    print("Netlify updated" if r.returncode == 0 else f"Netlify update failed: {r.stderr.strip()[:200]}")
    print("Redeploy so the change is live:  cd dashboard && netlify deploy --dir dist --functions netlify/functions --prod --site character-lab-research --no-build")
if cmd == "add":
    print(f"\nKey for {name} (send it privately, it is shown only here):\n{keys[name]}\n")
print("Collaborators:", ", ".join(sorted(keys)) or "none")
