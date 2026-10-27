[![KSUG.AI](ai-app/static/ksug-ai-logo.png)](https://ksug.ai)

# KSUG.AI · Cloud rehearsal: 27 October 2026

The merged AI recovery demo was exercised on a real one-node GKE Standard cluster.

| Component | Tested configuration |
| --- | --- |
| GKE | 1.36.4-gke.2046003, Regular channel |
| Worker | One e2-standard-2, COS_CONTAINERD |
| Zone | us-central1-c |
| Velero | v1.18.1 |
| GCP plugin | v1.14.4 |
| PostgreSQL | postgres:17.6-bookworm |
| AI mode | Extractive rehearsal mode; no model endpoint |
| Authentication | GKE Workload Identity; no service-account key |

## Results

1. Cloud Build built the app image and pushed it to a dedicated Artifact Registry repository.
2. PostgreSQL, the AI app, Velero, and node-agent became ready. The backup storage location was Available.
3. Uploaded `ai-app/sample-docs/recovery-plan.md` through the live HTTP upload API and asked the recovery-passphrase question. The response contained `nebula-orchid-42`. Checked the document and saved conversation in Chrome.
4. `./demo.sh backup rehearsal-01` completed: 49 Kubernetes items, two completed Kopia volume backups (`documents` and `backup`), two hooks attempted, zero hook failures.
5. `./demo.sh verify` confirmed the backup checkpoint before deletion.
6. Deleted the `velero-demo` namespace and waited for deletion to finish.
7. `./demo.sh restore rehearsal-01` completed, restored both PVCs onto newly provisioned volumes, imported the database dump, and verified the original rows, document contents, catalog, and conversation history. No seed commands were run after deletion.
8. The complete `/api/state` JSON before deletion and after restore was identical: one document and one conversation. The browser displayed the recovered document and original conversation.
9. An immediate backup using `--from-schedule postgres-hourly` completed successfully. This validates the schedule template, not an elapsed hourly timer.

The first cluster creation attempt in us-central1-f failed with GCE_STOCKOUT. The failed cluster was deleted and creation succeeded in us-central1-c. Capacity varies; override `MY_ZONE` and keep that value in every terminal used for the demo.

## Restore warnings reviewed

The restore completed with zero errors and warning categories for missing optional `VolumeGroupSnapshotContent` v1beta2 discovery and an already regenerated `kube-root-ca.crt` ConfigMap. This demo uses file system backup, not group snapshots; Kubernetes generated the namespace CA ConfigMap. Both volume restores completed and the application state comparison passed. These warnings did not prevent the tested recovery.

## Reconnect to an existing deployment

Set the project and zone to the values used when creating your cluster:

```bash
export MY_PROJECT_ID=your-project-id
export MY_ZONE=us-central1-c
source ./setenv.sh
gcloud container clusters get-credentials "$MY_CLUSTER" --project "$MY_PROJECT_ID" --zone "$MY_ZONE"
kubectl -n velero-demo port-forward svc/ai-assistant 8080:8080
```

Open http://127.0.0.1:8080. A port-forward must be restarted after namespace deletion. The app and hourly schedule were left running after the recovery rehearsal, then removed during the automated cleanup rehearsal below. Recreate the demo before using these reconnect commands again.

## Remaining limits

Ollama-generated answers, cross-cluster recovery, production hardening, and recovery under concurrent writes were not tested. Keep the app idle during a backup. The local behavior suite still uses mocked database calls; the cloud rehearsal separately covered the real PostgreSQL dump/import and HTTP app workflow.

## Automated cleanup rehearsal

On 27 October 2026, `cleanup.sh --apply --yes` removed the dedicated GKE cluster, remaining labeled disks, live backup bucket, Artifact Registry repository, exact Cloud Build source generations, and Velero service account. The final apply verification found no targeted live resources, including no GKE-named compute/network leftovers. The script supports a read-only preview and reruns after partial cleanup.

The actual run exposed Google's ambiguous response when describing a deleted service account and an alternate GCS 404 format; absence checks now use the service-account collection and recognize the observed GCS missing-object responses while preserving real permission errors. The local suite has 25 passing tests covering app behavior, CLI guards, and cleanup safety.

The shared build bucket retained two soft-deleted source archives (31,702 bytes total), with recorded expiry on 3 November 2026. Previously soft-deleted backup versions also remain under their original retention. Shared build buckets, completed build history, provider-managed logs, and unrelated project resources were preserved. See [automated cleanup](docs/CLEANUP.md) for billing and retention boundaries.
