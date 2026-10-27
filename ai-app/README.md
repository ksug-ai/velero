[![KSUG.AI](../ai-app/static/ksug-ai-logo.png)](https://ksug.ai)

# KSUG.AI Aurora AI demo app

A small document Q&A app for showing recovery of knowledge documents and conversations. Text and Markdown files live on a PVC. The document catalog and conversation history live in PostgreSQL. No embedding service or vector database is required.

## Deploy on GKE

From the repository root, first deploy PostgreSQL, then build and deploy the app:

```bash
export MY_PROJECT_ID=automatic-hawk-379007 # Replace this with your own project id
printf '\n'

./postgresql-deploy.sh
printf '\n'

./ai-app/build-and-push.sh
printf '\n'

kubectl -n velero-demo port-forward svc/ai-assistant 8080:8080
```

The build command builds, pushes, and deploys automatically, waits for rollout, and checks that the `ai-assistant` Service exists. It checks the cluster context and PostgreSQL before starting a billed build. To provision the whole demo, including GKE and Velero, use `./setup.sh` from the repository root instead.

For a build without deployment, use `./ai-app/build-and-push.sh --build-only`. Its output explicitly says that the app has not been deployed. To deploy a previously built image, use `AI_APP_IMAGE=your-image ./ai-app-deploy.sh`.

Open http://localhost:8080 and upload `sample-docs/recovery-plan.md`. Ask "What is the recovery passphrase?". The default mode returns matching document paragraphs and explicitly labels them as excerpts, with no language model involved. File uploads accept UTF-8 `.txt` and `.md` files up to roughly 256 KiB including the multipart request overhead.

The service has no authentication. Keep it private and use fictional documents. Uploaded files, questions, answers, and the demo database Secret are part of the backup.

## Optional Ollama model

Use an already-running Ollama endpoint reachable **from the app pod**, with a model already pulled. `localhost` in a pod does not refer to your laptop. The one-node GKE demo does not deploy a model or provision GPUs.

```bash
kubectl -n velero-demo patch configmap ai-settings --type merge -p '{"data":{"ANSWER_MODE":"ollama","OLLAMA_URL":"http://YOUR-REACHABLE-OLLAMA:11434","OLLAMA_MODEL":"llama3.2:1b"}}'
printf '\n'

kubectl -n velero-demo rollout restart deployment/ai-assistant
printf '\n'

kubectl -n velero-demo rollout status deployment/ai-assistant
```

Restart the port-forward after the pod changes. The UI shows the active mode. Retrieval selects up to three matching paragraphs to send to [Ollama's generate API](https://github.com/ollama/ollama/blob/main/docs/api.md); model errors are shown explicitly. The model only sees the selected paragraphs and current question, not previous conversations. Generated answers can be wrong; use the document checksums and saved history as the recovery evidence.

To return to the credential-free rehearsal:

```bash
kubectl -n velero-demo patch configmap ai-settings --type merge -p '{"data":{"ANSWER_MODE":"extractive"}}'
printf '\n'

kubectl -n velero-demo rollout restart deployment/ai-assistant
```

Reapplying `ai-app-deploy.sh` resets settings to the manifest defaults. Ollama credentials, if your endpoint needs them, are not supported by this minimal integration; use a private trusted endpoint.

## Local development and tests

Use Python 3.12+ and a local PostgreSQL instance. Create the `demo` database first; the app initializes its own tables on first use. The default `postgres` user is used only for this disposable demo.

```bash
python3 -m venv .venv
printf '\n'

.venv/bin/pip install -r ai-app/requirements.txt
printf '\n'

mkdir -p /tmp/aurora-documents
printf '\n'

export PGHOST=127.0.0.1 PGDATABASE=demo PGUSER=postgres
printf '\n'

export PGPASSWORD=your-local-demo-password
printf '\n'

export DOCUMENT_DIR=/tmp/aurora-documents
printf '\n'

.venv/bin/flask --app ai-app/app.py run --port 8080
```

Run behavior tests from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

These tests mock database calls and cover uploads, validation, document checksums, retrieval, model failure, and checkpoint mismatch detection. They do not replace an actual PostgreSQL dump/import or a GKE/Velero rehearsal. The checkpoint command hashes conversation contents and records document identities and SHA-256 hashes; verification reads recovered state without seeding it.
