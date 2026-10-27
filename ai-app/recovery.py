"""Checkpoint on backup; compare restored state without reseeding it."""
import hashlib
import json
import sys

from app import DATA, db, load_documents


def snapshot():
    with db() as conn:
        rows, _ = load_documents(conn)  # Includes full-file checksum verification.
        turns = conn.execute('SELECT id, question, answer, mode, sources FROM conversations ORDER BY id').fetchall()
    if not rows or not turns:
        raise RuntimeError('Upload a document and ask a question before backing up or verifying the AI demo.')
    documents = sorted((r['id'], r['name'], r['sha256']) for r in rows)
    digest = hashlib.sha256(json.dumps(turns, sort_keys=True).encode()).hexdigest()
    return {'documents': documents, 'conversations': len(turns), 'history_sha256': digest}


def main():
    state = snapshot()
    path = DATA / '.recovery-checkpoint.json'
    if sys.argv[1:] == ['checkpoint']:
        path.write_text(json.dumps(state, sort_keys=True))
        print('Saved recovery checkpoint:', len(state['documents']), 'documents;', state['conversations'], 'conversations')
    elif sys.argv[1:] == ['verify']:
        # Round-trip normalizes tuples to JSON lists.
        if json.loads(json.dumps(state)) != json.loads(path.read_text()):
            raise RuntimeError('Restored state does not match the backup checkpoint')
        print('Recovery verified: document contents, metadata, and conversation history match the backup checkpoint.')
    else:
        raise SystemExit('Usage: python recovery.py {checkpoint|verify}')


if __name__ == '__main__':
    main()
