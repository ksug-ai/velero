[![KSUG.AI](ai-app/static/ksug-ai-logo.png)](https://ksug.ai)

# KSUG.AI · Presenter runbook: recover the AI assistant

## 1. Prepare before presenting

Follow the README quick start: `./setup.sh` deploys the whole demo, including the app Service. The standalone `./ai-app/build-and-push.sh` also builds and deploys automatically. Allow time for cluster provisioning, image downloads, IAM propagation, and the first file system backup. Keep a second terminal available for observing resources.

```bash
kubectl get nodes
kubectl -n velero get pods
velero backup-location get
kubectl -n velero-demo get pods,pvc
kubectl -n velero-demo port-forward svc/ai-assistant 8080:8080
```

Open http://localhost:8080. Upload `ai-app/sample-docs/recovery-plan.md` and ask **"What is the recovery passphrase?"**. Show the answer `nebula-orchid-42` and the saved conversation. Add your own document or question for a more personal proof. Keep the app idle during backup.

Expected: ready PostgreSQL and AI assistant pods, two bound PVCs, an available backup location, an uploaded document, and a saved conversation. Do not redeploy or seed the application after deleting it during the restore demonstration.

## 2. Explain the backup path

Show the [architecture diagram](README.md#architecture) before running the backup. Use the [restore sequence](docs/ARCHITECTURE.md#restore-sequence) to explain what will happen after namespace deletion.

Kubernetes resources describe the application. A database-aware pre-backup hook produces a consistent `pg_dump`. The node-agent copies the dump PVC and the AI document PVC to GCS. An app hook stores a checkpoint of document hashes and conversation history. A Kubernetes YAML backup alone would not recover the rows. This demo uses file system backup, with cloud disk snapshots disabled; it does not demonstrate CSI snapshots, point-in-time recovery, or recovery to a different cluster.

```bash
cat manifests/postgresql.yaml
cat manifests/ai-app.yaml
cat velero-schedule.yaml
./demo.sh backup demo-01
velero backup describe demo-01 --details
kubectl -n velero get podvolumebackups
```

Use a new backup name on every run. Before deletion, check that the backup phase and its PodVolumeBackup are `Completed`, with no hook or volume errors. `demo.sh backup` requires a completed backup and completed backups for the `backup` and `documents` volumes. Run `./demo.sh verify` after backup to check the checkpoint before deletion.

## 3. Simulate application loss

```bash
./postgresql-destroy.sh
kubectl get namespace velero-demo
```

The script asks you to type the configured cluster name. The namespace lookup should report `NotFound`. The backup lives outside the cluster in GCS.

## 4. Restore and prove recovery

```bash
./demo.sh restore demo-01
```

The script refuses to restore over an existing demo namespace. It waits for the Velero restore to complete, waits for PostgreSQL, imports the recovered dump, and verifies the original rows, document file checksums, document catalog, and complete conversation history against the saved checkpoint. It does not run the seed command. Show the restore details as supporting evidence:

```bash
velero restore get
velero restore describe RESTORE_NAME --details
kubectl -n velero get podvolumerestores
./demo.sh verify
```

The old port-forward ends when the namespace is deleted. Start it again:

```bash
kubectl -n velero-demo port-forward svc/ai-assistant 8080:8080
```

Reload the browser. Show the recovered knowledge document and the **existing conversation before asking anything new**. The automated recovery check compares all saved conversation contents; a new question intentionally changes that history. Ask the same question again to show that the recovered knowledge is usable.

A restored pod alone is not proof of recovery. Neither the restore script nor the app generates missing demo documents or conversations.

## 5. Show automation

The installer applies an hourly schedule in UTC with 24-hour retention. Each scheduled backup also runs the dump and app checkpoint hooks. Upload a document and ask a question before the first scheduled run. Keep the app idle during scheduled runs as well; do not overlap manual and scheduled backups. Trigger it immediately instead of waiting for the next hour:

```bash
velero schedule get
velero backup create scheduled-demo-01 --from-schedule postgres-hourly --wait
velero backup describe scheduled-demo-01 --details
```

Deleting the application also removes the namespace targeted by the schedule. Restore promptly, and inspect scheduled backups for failures before relying on them.

## Troubleshooting

- Wrong context: reconnect using the exact project, zone, and cluster from `setenv.sh`.
- Bucket unavailable: inspect `velero backup-location get` and `kubectl -n velero logs deployment/velero`. Check the bucket IAM binding, annotated `velero` service account, and GKE workload pool. IAM propagation can take time; retry after it settles.
- Backup fails: use `velero backup logs BACKUP_NAME` and `velero backup describe BACKUP_NAME --details`. A failing `pg_dump` must stop the backup; never delete the namespace after a failed or partially failed backup.
- Volume backup/restore stalls: inspect node-agent logs and `podvolumebackups` / `podvolumerestores` in the Velero namespace. File system backup requires node access to pod volumes, so this setup targets GKE Standard, not Autopilot.
- App image pull fails: ensure the image tag exists and the GKE node identity has Artifact Registry Reader access.
- Recovery checkpoint mismatch: compare document PVC contents and the restored database. Check whether someone uploaded or chatted during backup. Do not reseed to hide a failed recovery.
- Model unavailable: return to extractive mode using the steps in `ai-app/README.md`; documents and chat history remain intact.
- PostgreSQL pending: inspect pod events, PVC events, and availability of the GKE `standard-rwo` StorageClass.
- SQL import fails: keep the restored namespace and inspect `/backup/demo.dump`, pod logs, and restore details before retrying. You can rerun the `pg_restore` command from `demo.sh` after resolving the issue.

## Cleanup

Use the automated teardown after the demo. It removes the cluster, labeled disks, backup bucket, image repository, exact demo build artifacts, and the Velero service account, then verifies the result.

```bash
export MY_PROJECT_ID=your-project-id
export MY_ZONE=us-central1-c  # Match the zone you actually deployed
./cleanup.sh
./cleanup.sh --apply
```

The first command previews the scope. The second requires a typed project/cluster confirmation and permanently deletes the demo backups as well. For unattended runs, use `./cleanup.sh --apply --yes`.

See [the cleanup guide](docs/CLEANUP.md) for resource scope, reruns, JSON reports, retained build artifacts, and billing limits. The older `gke-destroy.sh` and `velero-destroy.sh` scripts only remove their named components; they do not perform the full teardown.
