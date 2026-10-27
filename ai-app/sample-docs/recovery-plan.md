# Aurora AI recovery plan

Aurora AI is our internal document assistant. Its knowledge documents live on a Kubernetes persistent volume. Its document catalog and conversation history live in PostgreSQL.

The recovery passphrase is nebula-orchid-42. This is a fictional demo marker, not a credential. Seeing this phrase after recovery proves that the uploaded knowledge document returned.

Velero protects the Kubernetes resources and document volume. Before each backup, a database hook writes a consistent PostgreSQL dump to a separate volume. The Velero node-agent copies the dump and documents to Google Cloud Storage.

After accidental namespace deletion, restore the Kubernetes resources and both backed-up volumes, import the database dump, and verify the document checksum and previous conversation. The model weights can be downloaded again; the team's documents and conversations are the valuable state.
