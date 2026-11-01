#!/bin/bash
# Safety check: looks for secrets, personal data and files that must never be
# committed. Read-only: it never changes git state.
# Run it BEFORE `git add`, `git commit` and `git push`.
# Scans: tracked files (working tree), staged content (index), and untracked
# files that are not ignored.
# Usage: bash scripts/precommit_check.sh
# Exit codes: 0 = OK, 1 = problems found, 2 = not a git repository.
set -u

root=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "ERROR: not a git repository" >&2; exit 2; }
cd "$root" || exit 2

FINDINGS=0
SCANNED=0
# Globals describing the file currently being scanned (set by scan_file).
DISPLAY_NAME=""   # path shown in reports
READ_PATH=""      # real file to read (working-tree file or temp copy of a staged blob)
SRC=""            # worktree | staged | untracked

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Print one finding. $3 is the matched text; only the first 6 chars are shown.
report() {
  local where="$1" check="$2" match="${3:-}"
  if [ -n "$match" ]; then
    echo "FOUND  $where  ($SRC)  [$check]  ${match:0:6}..."
  else
    echo "FOUND  $where  ($SRC)  [$check]"
  fi
  FINDINGS=$((FINDINGS + 1))
}

# ---- Check 1: forbidden paths (case-insensitive, any depth) ----
# A leading "/" is added so that "*/name" also matches a file at the top level.
check_path() {
  local f="$1" p
  p="/$(printf '%s' "$f" | tr 'A-Z' 'a-z')"
  case "$p" in
    */.env.example) return ;;   # the template file is allowed
  esac
  case "$p" in
    */.env|*/.env.*|*.docx|*/.venv/*|*.pem|*.key|*.p12|*.keystore|*.secret|\
*/id_rsa*|*/id_ed25519*|*/id_ecdsa*|*/id_dsa*|*/deploy_key*|*/wallet*.json|*/claude.md|*/.claude/*|*/notes_ja/*|*/secrets/*|\
*/keystore/*|/docs/handoff.md|*/.streamlit/secrets.toml|*/to\ do\ for\ noa*)
      report "$f" "forbidden path" ;;
  esac
}

# ---- Content checks (all read $READ_PATH, report $DISPLAY_NAME) ----
# scan_pattern LABEL REGEX [grep flags]: report every match as file:line.
scan_pattern() {
  local label="$1" regex="$2" flags="${3:-}" line
  # shellcheck disable=SC2086
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    report "$DISPLAY_NAME:${line%%:*}" "$label" "${line#*:}"
  done < <(grep -n -o -E $flags -e "$regex" "$READ_PATH" 2>/dev/null)
}

# 64-hex private key: whole token, with or without 0x. A bare token is only
# reported if the line has 0x on it or says key/secret/private/mnemonic.
scan_hex_keys() {
  local line text lower hex
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    text="${line#*:}"
    lower="$(printf '%s' "$text" | tr 'A-Z' 'a-z')"
    if printf '%s' "$lower" | grep -q -E '(^|[^0-9a-z])0x[0-9a-f]{64}([^0-9a-z]|$)' \
       || printf '%s' "$lower" | grep -q -E 'key|secret|private|mnemonic'; then
      hex="$(printf '%s' "$lower" | grep -o -E '(0x)?[0-9a-f]{64}' | head -n 1)"
      report "$DISPLAY_NAME:${line%%:*}" "64-hex private key" "$hex"
    fi
  done < <(grep -n -i -E -e '(^|[^0-9A-Za-z])(0x)?[0-9a-fA-F]{64}([^0-9A-Za-z]|$)' "$READ_PATH" 2>/dev/null)
}

# Emails: skip noreply GitHub addresses and example.com/org/net domains.
scan_emails() {
  local line m lower
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    m="${line#*:}"
    lower="$(printf '%s' "$m" | tr 'A-Z' 'a-z')"
    case "$lower" in
      *@users.noreply.github.com|*@example.com|*@example.org|*@example.net) continue ;;
    esac
    report "$DISPLAY_NAME:${line%%:*}" "email address" "$m"
  done < <(grep -n -o -E -e '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$READ_PATH" 2>/dev/null)
}

# Phone numbers: ONLY formatted shapes (with + / spaces / hyphens). Bare digit
# runs are deliberately ignored, because CSV values such as 119484066.0 or
# 796560.44 and id columns are plain numbers and would cause false alarms.
# The leading (^|[^0-9=-]) stops matches in the middle of longer digit/date
# strings and right after "=" (URL query strings such as id=090-1234-5678).
# Known gap: a real phone number written as "tel=090-..." is not caught.
scan_phones() {
  local line m
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    m="${line#*:}"
    m="$(printf '%s' "$m" | sed -E 's/^[^0-9+(]//')"
    report "$DISPLAY_NAME:${line%%:*}" "phone number" "$m"
  done < <(grep -n -o -E \
    -e '(^|[^0-9=-])(\+[0-9]{1,3}[ -]?[0-9]{1,4}[ -][0-9]{2,4}[ -][0-9]{3,4}|\(?0[0-9]{1,4}\)?-[0-9]{2,4}-[0-9]{3,4})' \
    "$READ_PATH" 2>/dev/null)
}

check_content() {
  # Check 2: API keys and private keys
  scan_pattern "API key (sk-)"       'sk-[A-Za-z0-9_-]{20,}'
  scan_pattern "GitHub token"        'gh[pous]_[A-Za-z0-9]{20,}'
  scan_pattern "AWS access key"      'AKIA[0-9A-Z]{16}'
  scan_pattern "private key block"   '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  # Credentials assigned in text: password=xxxx, AWS_SECRET_ACCESS_KEY=xxxx
  scan_pattern "password assignment" '(password|passwd)[[:space:]]*[:=][[:space:]]*["'"'"']?[^[:space:]"'"'"']{4,}' "-i"
  scan_pattern "AWS secret assignment" 'AWS_SECRET[A-Z_]*[[:space:]]*[:=][[:space:]]*["'"'"']?[^[:space:]"'"'"']{8,}' "-i"
  # Check 3: crypto secrets
  scan_hex_keys
  scan_pattern "seed phrase wording" 'seed phrase|mnemonic|recovery phrase' "-i"
  scan_pattern "seed phrase (JP)"    'シードフレーズ|秘密鍵'
  # Check 4: email addresses
  scan_emails
  # Check 5: phone numbers
  scan_phones
  # Check 6: absolute home paths
  scan_pattern "home path"           '/(Users|home)/[A-Za-z0-9._-]+/'
}

# scan_file DISPLAY READ_PATH SRC: run content checks on one text file.
scan_file() {
  DISPLAY_NAME="$1"; READ_PATH="$2"; SRC="$3"
  [ -f "$READ_PATH" ] || return
  grep -Iq . "$READ_PATH" 2>/dev/null || return   # skip binary/empty files
  SCANNED=$((SCANNED + 1))
  check_content
}

# True for files that contain the patterns on purpose.
is_excluded() {
  case "$1" in
    scripts/precommit_check.sh|docs/DO_NOT_COMMIT.md) return 0 ;;
  esac
  return 1
}

# ---- Main: tracked files (worktree + staged blob) ----
BLOB="$TMP_DIR/blob"
while IFS= read -r f; do
  [ -z "$f" ] && continue
  SRC="tracked"
  check_path "$f"
  is_excluded "$f" && continue
  scan_file "$f" "$f" "worktree"
  # Also scan the staged (index) version if it differs from the working tree.
  if git show ":$f" > "$BLOB" 2>/dev/null; then
    if [ ! -f "$f" ] || ! cmp -s "$BLOB" "$f"; then
      scan_file "$f" "$BLOB" "staged"
    fi
  fi
done < <(git -c core.quotepath=off ls-files)

# ---- Main: untracked files that are not ignored ----
while IFS= read -r f; do
  [ -z "$f" ] && continue
  SRC="untracked"
  check_path "$f"
  is_excluded "$f" && continue
  scan_file "$f" "$f" "untracked"
done < <(git -c core.quotepath=off ls-files --others --exclude-standard)

if [ "$FINDINGS" -gt 0 ]; then
  echo "FAILED: $FINDINGS problem(s) found ($SCANNED text files scanned)"
  exit 1
fi
echo "OK: no problems found ($SCANNED text files scanned)"
exit 0
