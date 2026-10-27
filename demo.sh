#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
require_context
sql() { kubectl -n velero-demo exec -i deployment/postgres -- psql -U postgres -d demo -v ON_ERROR_STOP=1 "$@"; }
check_backup() {
  local name="$1" phase phases backed_up_volumes volume actual found
  local expected_volumes=(backup documents)
  phase=$(kubectl -n velero get backup "$name" -o jsonpath='{.status.phase}')
  [[ "$phase" == Completed ]] || { echo "Backup $name is $phase, not Completed. Verification refused." >&2; exit 1; }
  phases=$(kubectl -n velero get podvolumebackups -l "velero.io/backup-name=$name" -o jsonpath='{range .items[*]}{.status.phase}{"\n"}{end}')
  [[ -n "$phases" ]] || { echo 'No volume backup found; refusing to report success.' >&2; exit 1; }
  while IFS= read -r phase; do
    [[ "$phase" == Completed ]] || { echo "Volume backup is $phase" >&2; exit 1; }
  done <<< "$phases"
  backed_up_volumes=$(kubectl -n velero get podvolumebackups -l "velero.io/backup-name=$name" -o jsonpath='{range .items[*]}{.spec.volume}{"\n"}{end}')
  for volume in "${expected_volumes[@]}"; do
    found=false
    while IFS= read -r actual; do [[ "$actual" != "$volume" ]] || found=true; done <<< "$backed_up_volumes"
    "$found" || { echo "Missing volume backup: $volume" >&2; exit 1; }
  done
}
case "${1:-}" in
  seed)
    sql <<'SQL'
CREATE TABLE IF NOT EXISTS messages (id integer PRIMARY KEY, message text NOT NULL);
INSERT INTO messages VALUES (1, 'Velero restored my PostgreSQL data'), (2, 'Automated backups on GKE') ON CONFLICT (id) DO NOTHING;
SQL
    ;;
  verify)
    name="${2:?Usage: ./demo.sh verify BACKUP_NAME}"
    check_backup "$name"
    sql <<'SQL'
DO $$ BEGIN
  IF (SELECT count(*) FROM messages WHERE
      (id = 1 AND message = 'Velero restored my PostgreSQL data') OR
      (id = 2 AND message = 'Automated backups on GKE')) <> 2 THEN
    RAISE EXCEPTION 'Expected demo rows are missing';
  END IF;
END $$;
TABLE messages;
SQL
    kubectl -n velero-demo get deployment/ai-assistant >/dev/null
    kubectl -n velero-demo exec deployment/ai-assistant -- python recovery.py verify >/dev/null
    echo "Backup $name is complete; current app data matches the local checkpoint."
    echo 'To prove recovery, delete the demo namespace and run demo.sh restore BACKUP_NAME.'
    ;;
  backup)
    name="${2:?Usage: ./demo.sh backup BACKUP_NAME}"
    ensure_velero
    kubectl -n velero rollout status deployment/velero --timeout=180s
    kubectl -n velero rollout status daemonset/node-agent --timeout=180s
    kubectl -n velero-demo get deployment/ai-assistant >/dev/null
    echo 'Pause uploads/questions until the backup finishes; both volume backups must complete.'
    velero backup create "$name" --include-namespaces velero-demo --snapshot-volumes=false --wait
    check_backup "$name"
    velero backup describe "$name" --details
    ;;
  restore)
    ensure_velero
    name="${2:?Usage: ./demo.sh restore BACKUP_NAME}"
    check_backup "$name"
    if kubectl get namespace velero-demo >/dev/null 2>&1; then
      echo 'Delete the demo namespace with ./postgresql-destroy.sh before restoring.' >&2; exit 1
    fi
    restore="${name}-$(date +%s)"
    velero restore create "$restore" --from-backup "$name" --wait
    [[ "$(kubectl -n velero get restore "$restore" -o jsonpath='{.status.phase}')" == Completed ]]
    kubectl -n velero-demo rollout status deployment/postgres --timeout=300s
    kubectl -n velero-demo exec deployment/postgres -- pg_restore -U postgres -d demo --clean --if-exists --exit-on-error /backup/demo.dump
    kubectl -n velero-demo rollout status deployment/ai-assistant --timeout=300s
    "$ROOT/demo.sh" verify "$name"
    echo "Restore $restore completed and recovered application state was verified."
    ;;
  *) echo 'Usage: ./demo.sh {seed|verify NAME|backup NAME|restore NAME}' >&2; exit 1 ;;
esac
