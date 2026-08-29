const body = document.querySelector('#documents');
const notice = document.querySelector('#notice');
const api = async (url, options = {}) => {
  const response = await fetch(url, {...options, credentials: 'same-origin'});
  if (response.status === 401) { location.href = '/admin'; throw new Error('Session expired'); }
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Request failed');
  return data;
};
const size = bytes => bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
async function load() {
  const [documents, readiness] = await Promise.all([api('/api/admin/documents'), api('/api/admin/documents/readiness')]);
  document.querySelector('#mode').textContent = readiness.ai_mode;
  const ready = document.querySelector('#readiness'); ready.textContent = `${readiness.status} — ${readiness.detail}`; ready.className = readiness.status === 'ready' ? 'ready' : 'not-ready';
  body.replaceChildren();
  for (const doc of documents) {
    const row = document.createElement('tr');
    const indexState = doc.indexing_error ? `${doc.indexing_status}: ${doc.indexing_error}` : doc.indexing_status;
    const values = [doc.filename, size(doc.size_bytes), new Date(doc.created_at).toLocaleString(), doc.chunks, `${doc.embedding_provider} / ${doc.embedding_model} (${doc.embedding_dimensions})`, indexState];
    values.forEach(value => { const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); });
    const actions = document.createElement('td'); actions.className = 'actions';
    const reindex = document.createElement('button'); reindex.textContent = 'Reindex'; reindex.onclick = () => act(`/api/admin/documents/${doc.id}/reindex`, 'POST');
    const remove = document.createElement('button'); remove.textContent = 'Delete'; remove.className = 'danger'; remove.onclick = () => { if (confirm(`Delete ${doc.filename}? This cannot be undone.`)) act(`/api/admin/documents/${doc.id}`, 'DELETE'); };
    actions.append(reindex, remove); row.appendChild(actions); body.appendChild(row);
  }
}
async function act(url, method) { try { const result = await api(url, {method}); notice.textContent = Number.isInteger(result.succeeded) ? `${result.status}: ${result.succeeded} succeeded, ${result.failed} failed` : result.status; await load(); } catch (error) { notice.textContent = error.message; await load(); } }
document.querySelector('#upload').addEventListener('submit', async event => { event.preventDefault(); const button = event.currentTarget.querySelector('button'); button.disabled = true; try { await api('/api/admin/documents', {method:'POST', body:new FormData(event.currentTarget)}); event.currentTarget.reset(); notice.textContent='Document uploaded'; await load(); } catch(error) { notice.textContent=error.message; } finally { button.disabled=false; } });
document.querySelector('#reindex-all').onclick = () => act('/api/admin/documents/reindex-incompatible', 'POST');
load().catch(error => { notice.textContent = error.message; });
