const $ = id => document.getElementById(id);
function element(tag, text, className) {
  const el = document.createElement(tag); el.textContent = text;
  if (className) el.className = className;
  return el;
}
async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
async function refresh() {
  const state = await api('/api/state');
  $('mode').textContent = state.mode === 'ollama' ? 'Model connected · Ollama' : 'Rehearsal mode · document excerpts, no LLM';
  $('documents').replaceChildren(...state.documents.map(doc => {
    const li = element('li', doc.name); li.append(element('small', `SHA-256 ${doc.sha256.slice(0, 12)}…`)); return li;
  }));
  $('history').replaceChildren();
  if (!state.conversations.length) $('history').append(element('p', 'Your conversation will appear here.', 'empty'));
  for (const turn of state.conversations) {
    const article = document.createElement('article');
    article.append(element('h3', turn.question), element('p', turn.answer, 'answer'), element('small', `${turn.mode} · ${new Date(turn.created_at).toLocaleString()}`));
    $('history').append(article);
  }
}
function handle(form, action) {
  form.addEventListener('submit', async event => {
    event.preventDefault(); const button = form.querySelector('button'); button.disabled = true;
    $('status').textContent = 'Working…';
    try { await action(); await refresh(); $('status').textContent = 'Saved.'; form.reset(); }
    catch (error) { $('status').textContent = error.message; }
    finally { button.disabled = false; }
  });
}
handle($('upload'), () => api('/api/documents', {method: 'POST', body: new FormData($('upload'))}));
handle($('chat'), () => api('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question: $('question').value})}));
refresh().catch(error => { $('status').textContent = error.message; });
