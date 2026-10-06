#!/bin/sh
# Push every deliverable to the shared Google Drive folder "INFLU TIB OUTIL EN LIGNE" (copy only: never deletes on Drive).
#   videos/<perso>/<perso>_<n>_4k.mp4   ready-to-post 4K videos (all batches)
#   photos-profil/<perso>.jpg           Instagram profile pictures
#   persos/<perso>.jpg                  full-body HD character images (Genjutsu references)
#   kits/batch<N>_POSTING.md            posting kits (bio, link, order, captions)
# Needs the rclone remote "gdrive" (rclone config create gdrive drive scope=drive).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
FOLDER="${DRIVE_FOLDER_ID:?set DRIVE_FOLDER_ID}"
R="rclone --drive-root-folder-id $FOLDER --transfers 6 --stats-one-line --stats 30s --exclude .DS_Store"

for b in "$ROOT"/output/batch*; do
  [ -d "$b/4k" ] && $R copy "$b/4k" gdrive:videos
  [ -f "$b/POSTING.md" ] && $R copyto "$b/POSTING.md" "gdrive:kits/$(basename "$b")_POSTING.md"
done
$R copy "$ROOT/dashboard/img/pfp/hd" gdrive:photos-profil
# character images named by id instead of lab_xx
python3 - "$ROOT" <<'EOF'
import json, os, shutil, sys
root = sys.argv[1]; out = f"{root}/output/drive_persos"; os.makedirs(out, exist_ok=True)
for c in json.load(open(f"{root}/dashboard/dist/characters.json"))["characters"]:
    src = f"{root}/dashboard/img/hd/{c['images']['hd_1080x1920'].split('/')[-1]}"
    if os.path.exists(src): shutil.copy2(src, f"{out}/{c['id']}.jpg")
EOF
$R copy "$ROOT/output/drive_persos" gdrive:persos
echo "Drive sync done"
