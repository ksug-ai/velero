# Repository review and cleanup

## Findings addressed

| Inherited issue | Change |
| --- | --- |
| README and lab centered on KubeArmor/LLM security | Replaced with Velero overview and presenter runbook |
| Falco, KubeArmor, vulnerable LLM app, unrelated policies and guides | Removed from the working tree; original versions remain in Git history |
| Timestamp-generated cluster names and prefix-based deletion | Exact configured cluster name and project/zone on cloud commands |
| Cluster destruction also deleted disks and a guessed bucket | Cluster deletion only; backups retained for explicit cleanup |
| Downloaded long-lived GCP keys and broad project permissions | GKE Workload Identity and bucket-scoped object access; signing permission scoped to the demo service account |
| Fixed Linux-only CLI download into `~/gke` | Explicit CLI prerequisite and version check |
| Helm sample depended on an unpinned external chart | Standalone PostgreSQL manifest with a pinned image tag |
| Copying live PostgreSQL data without consistency handling | Logical dump hook, dedicated dump PVC, explicit SQL import |
| One-off backup without restore verification | Backup/restore commands, phase checks, recovered-row query, document checksums, and conversation checkpoint |
| Schedule creation failed on reruns; unspecified retention | Declarative apply, quoted cron, 24-hour TTL |
| Scripts depended on current directory and continued after errors | Script-relative paths, Bash shebangs, strict error handling, context checks |

## Remaining boundaries

This is a disposable presentation lab. PostgreSQL live storage is ephemeral, credentials are demo-only, image tags are not digest-locked, and availability is limited to one node. No production hardening, point-in-time recovery, automated cross-cluster recovery, or cloud deployment has been validated as part of this cleanup. The hourly schedule and backup hook must be rehearsed on the actual target cluster before the event.

The deployment scripts configure billed resources and IAM bindings. They were reviewed locally without provisioning cloud infrastructure. Existing resources with the configured names are assumed to be dedicated to this demo; choose fresh names if sharing a project.

## AI application demo

Added Aurora AI, a small document Q&A app, in place of the inherited command-injection app. It stores uploaded UTF-8 documents on a PVC, records catalog metadata and conversations in PostgreSQL, and supports a clearly labeled extractive rehearsal mode or an optional Ollama model. It uses a ClusterIP service with local port-forward access, not a public load balancer. The app checkpoint and dump hooks allow recovery verification without generating replacement data.

The two volume backups do not form an atomic distributed snapshot: keep the application idle during backups. Checkpoint verification detects inconsistent recovery. The app has no authentication or tenant isolation and is only for a private demo. Model availability, weights, and external service state are outside the backup scope. App deployment requires an image available to GKE; restored backups still depend on that image remaining in the registry.
