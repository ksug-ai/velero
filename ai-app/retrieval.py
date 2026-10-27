"""Small, transparent lexical retrieval; no embeddings or model downloads."""
import re

STOP = {"a", "an", "the", "is", "are", "to", "of", "and", "in", "it", "what", "how", "do", "does", "we", "our", "for"}


def retrieve(question, documents):
    terms = set(re.findall(r"\w+", question.lower())) - STOP
    ranked = []
    for name, content in documents:
        for paragraph in re.split(r"\n\s*\n", content):
            paragraph = paragraph.strip()
            words = set(re.findall(r"\w+", paragraph.lower()))
            score = len(terms & words)
            if paragraph and score:
                ranked.append((score, name, paragraph[:1800]))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [{"source": name, "text": paragraph} for _, name, paragraph in ranked[:3]]


def extractive_answer(excerpts):
    if not excerpts:
        return "I couldn't find matching information. Upload a text document or try different words."
    return "\n\n".join(f"[{e['source']}]\n{e['text']}" for e in excerpts)
