# Shared by pre-commit and pre-push: stop when the remote branch has commits we don't have yet.
# Bypass in an emergency: SKIP_PULL_CHECK=1 git commit … / git push …
check_remote() {
  action="$1"
  [ -n "$SKIP_PULL_CHECK" ] && return 0
  upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null) || {
    echo "pull-check: no upstream branch, check skipped"; return 0; }
  remote=${upstream%%/*}
  if ! git fetch --quiet "$remote" 2>/dev/null; then
    echo "pull-check: could not reach '$remote', check skipped (offline?)"; return 0
  fi
  behind=$(git rev-list --count HEAD.."$upstream")
  if [ "$behind" -gt 0 ]; then
    echo ""
    echo "✋ $behind new commit(s) on $upstream that you don't have yet:"
    git log --oneline --no-decorate HEAD.."$upstream" | head -10
    echo ""
    echo "   Run:  git pull --rebase --autostash"
    echo "   then: git $action again."
    echo ""
    exit 1
  fi
  return 0
}
