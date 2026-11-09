#!/bin/sh
# Daily off-server backup: a consistent SQLite copy uploaded to a private S3-compatible bucket.
# Bucket-side lifecycle rules own long-term retention; this script only prunes the local copies.
set -eu

: "${B2_BUCKET:?B2_BUCKET is not set}"
: "${B2_ENDPOINT:?B2_ENDPOINT is not set}"
: "${B2_REGION:?B2_REGION is not set}"
: "${B2_KEY_ID:?B2_KEY_ID is not set}"
: "${B2_APP_KEY:?B2_APP_KEY is not set}"

LOCAL_KEEP_DAYS=7
backup_dir="$(dirname "${SCANNER_DB_PATH:-/app/data/expenses.sqlite3}")/backups"
name="expenses-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
path="$backup_dir/$name"

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
python -m scanner.backup --output "$path"

# S3 rejects unsigned bodies unless the payload hash is declared and signed.
payload_sha256="$(sha256sum "$path" | cut -d ' ' -f 1)"
# Credentials go through curl's stdin config so they never appear in the process list.
printf 'user = "%s:%s"\n' "$B2_KEY_ID" "$B2_APP_KEY" | curl --config - \
    --fail --silent --show-error --max-time 300 \
    --aws-sigv4 "aws:amz:${B2_REGION}:s3" \
    --header "x-amz-content-sha256: ${payload_sha256}" \
    --upload-file "$path" \
    "${B2_ENDPOINT%/}/${B2_BUCKET}/${name}"

find "$backup_dir" -name 'expenses-*.sqlite3' -type f -mtime +"$LOCAL_KEEP_DAYS" -delete
echo "Uploaded $name (sha256 $payload_sha256)."
