[![KSUG.AI](../ai-app/static/ksug-ai-logo.png)](https://ksug.ai)

# KSUG.AI · Automated demo cleanup

`cleanup.sh` removes the dedicated GKE/Velero/AI demo and verifies the result. It previews by default and is safe to rerun after an interrupted or partial cleanup. It requires Bash, Python 3, `gcloud`, `kubectl`, and the GKE auth plugin. Velero CLI is not required: deleting the cluster removes the server, node-agent, schedules, and other in-cluster resources.

## Run

Use the **same project, cluster, zone, region, bucket, and service-account settings** used for deployment. The live rehearsal used `us-central1-c`; the defaults in `setenv.sh` use `us-central1-f`. A wrong zone is rejected if the cluster exists in another zone.

```bash
export MY_PROJECT_ID=your-project-id
export MY_ZONE=us-central1-c
./cleanup.sh                        # Read-only cloud inventory; writes cleanup-report.json
./cleanup.sh --apply                # Show scope, then require project/cluster confirmation
```

For an unattended teardown of the configured dedicated demo:

```bash
./cleanup.sh --apply --yes --report /tmp/velero-cleanup-report.json
```

`--yes` skips the typed confirmation; `--apply` is still required. Every cloud command explicitly selects the project, and Kubernetes commands explicitly select the expected cluster context. The default report file is ignored by Git.

## Deletion order and scope

1. Discover resources and exact Cloud Build source generations. Abort on inventory permission errors or a mismatched cluster zone.
2. Cancel any active builds whose output images all belong to this demo's repository.
3. Pause the hourly backup schedule and delete the `velero-demo` namespace while GKE can reclaim PVC disks. If Kubernetes is unreachable, attempt cluster deletion and report the namespace-cleanup warning.
4. Delete the exact configured cluster and then remove any disks labeled with **both** its cluster name and zone. Disks belonging to other workloads are excluded.
5. Disable soft delete on the **dedicated** demo backup bucket, then delete that bucket and all live/noncurrent backup objects. This permanently removes the recovery copies.
6. Delete the dedicated `velero-demo` Artifact Registry repository in `MY_REGION`, including all its images.
7. Delete only source archive generations referenced by matching global Cloud Build records. Delete matching build log objects only when they reside in a bucket owned by this project. Shared buckets are preserved.
8. Delete the configured Velero Google service account and its resource-level IAM policy.
9. Re-inventory and report remaining targeted live resources. Also flag GKE-named VM, snapshot, address, forwarding-rule, firewall-rule, and route leftovers for inspection.

The bucket, repository, cluster, and service account must be dedicated to this demo. The repository name is `velero-demo`, matching the build script. The script does not delete the GCP project, default network, shared buckets, APIs, unrelated disks/VMs, old workshops, or unrelated IAM policies. Unproven network leftovers are reported rather than deleted by a guessed name. A failed action or a remaining targeted live resource produces a nonzero exit code; fix the reported issue and rerun.

## Retention and billing limits

Removing live resources stops their ongoing use; it does not reverse charges already incurred. Google Cloud billing data can lag behind deletion.

Soft-deleted objects created **before** the dedicated bucket's policy is cleared cannot be purged early, as described in [Google Cloud's soft-delete documentation](https://docs.cloud.google.com/storage/docs/soft-delete). Shared Cloud Build buckets retain their existing soft-delete/retention policies, so deleted build source generations can remain temporarily. The final JSON report records any matching retained source metadata, including the retention timestamps returned by GCS. Do not treat “no targeted live resources remain” as proof that all retained bytes or all project charges are gone.

Completed Cloud Build history, provider-managed build logs, and project-wide logging policies remain. Deleting a service account also follows Google's account recovery window. The script does not weaken retention or logging protections on shared resources.

## Verify

The apply run prints a final verification result and saves `remaining_resources`, `retained_soft_deleted_objects`, `warnings`, and `errors` in the JSON report. Run the preview again to confirm the resources remain absent. Review unrelated resources separately in Google Cloud if you want to reduce the rest of the project's charges.
