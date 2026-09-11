const fileSave = {
  supported: typeof window.showSaveFilePicker === 'function' && window.isSecureContext,
  handle: null, key: null, ready: false, busy: false,
  savedContent: null, savedName: '', draftStored: false, error: ''
};
let fileHandleDB;
function projectStamp(value) {
  const {updatedAt, ...content} = value;
  return JSON.stringify(content);
}
function currentHtmlName() {
  const name = decodeURIComponent(location.pathname.split('/').pop() || '');
  return /\.html?$/i.test(name) ? name : filename('html');
}
function fileTargetKey() {return location.href.split('#')[0] + '::' + project.id;}
function openFileHandleDB() {
  if (!fileHandleDB) fileHandleDB = new Promise((resolve, reject) => {
    const request = indexedDB.open('zt-homelab-file-targets', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('targets');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(Error('文件授权记录暂时不可用'));
  });
  return fileHandleDB;
}
async function fileTargetStore(key, handle) {
  const db = await openFileHandleDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('targets', handle ? 'readwrite' : 'readonly');
    const store = tx.objectStore('targets');
    const request = handle ? store.put(handle, key) : store.get(key);
    tx.oncomplete = () => resolve(request.result);
    tx.onerror = tx.onabort = () => reject(tx.error || Error('文件授权记录不可用'));
  });
}
function restoreSaveTarget() {
  const key = fileTargetKey();
  if (key === fileSave.key) return;
  fileSave.key = key;
  fileSave.handle = null;
  fileSave.ready = !fileSave.supported;
  if (!fileSave.supported) return;
  fileTargetStore(key).then(handle => {
    if (key === fileSave.key && handle?.kind === 'file') fileSave.handle = handle;
  }).catch(() => {}).finally(() => {
    if (key === fileSave.key) {fileSave.ready = true; renderSaveState();}
  });
}
function renderSaveState() {
  const clean = fileSave.savedContent === projectStamp(project);
  const status = fileSave.busy ? '正在写入 HTML…'
    : fileSave.error ? '写入失败 · HTML 待保存'
    : clean ? 'HTML 已保存'
    : fileSave.draftStored ? '草稿已保存 · HTML 待保存' : 'HTML 待保存 · 草稿不可用';
  $('#save-state').textContent = status;
  $('#save-state').title = fileSave.error || (clean ? fileSave.savedName : '草稿仅保存在当前浏览器中');
  const btn = $('#save-btn');
  const label = fileSave.supported ? '覆盖保存' : '另存为 HTML';
  // Keep the click target stable when an input commits on pointer-down.
  if (btn.dataset.saveLabel !== label) {
    btn.innerHTML = icon('Save') + `<span>${label}</span>`;
    btn.dataset.saveLabel = label;
  }
  btn.disabled = fileSave.busy || !fileSave.ready;
  btn.title = fileSave.supported ? (fileSave.handle ? `写入 ${fileSave.handle.name}` : '首次保存需选择并授权目标 HTML 文件') : '当前浏览器不支持直接覆盖；下载可编辑 HTML 副本';
  btn.setAttribute('aria-label', fileSave.supported ? '覆盖保存 HTML' : '另存为 HTML');
  const choose = $('#choose-save-target');
  if (choose) choose.disabled = fileSave.busy || !fileSave.ready;
  const target = $('#save-target-name');
  if (target) target.textContent = fileSave.handle?.name || (fileSave.supported ? '尚未选择目标 HTML' : '下载文件');
}
function setupFileSaving() {
  $('#file-save-options')?.remove();
  const box = document.createElement('section');
  box.id = 'file-save-options';
  box.className = 'file-save-options';
  box.innerHTML = `<div class="file-save-target"><strong>保存位置</strong><span id="save-target-name"></span></div><p class="muted">${fileSave.supported ? '首次选择已有 HTML 并授权后，保存将直接写回选中的文件。' : '当前浏览器不支持直接覆盖本地文件。Firefox 可下载 HTML，再手动替换原文件；自动覆盖请使用 Chrome / Edge。'}</p>${fileSave.supported ? `<button id="choose-save-target" class="export-row">${icon('FolderOpen')}<span><strong>选择其他 HTML 保存</strong><small>更换后，后续保存写入新选中的文件</small></span>${icon('ChevronRight')}</button>` : ''}`;
  $('#export-dialog .dialog-content').prepend(box);
  if ($('#choose-save-target')) $('#choose-save-target').onclick = () => saveTopology(true);
  fileSave.savedContent = embedded ? projectStamp(embedded) : null;
  fileSave.savedName = embedded ? currentHtmlName() : '';
}
function commitPendingEdits() {
  const form = $('#inspector form');
  if (form && !form.reportValidity()) return false;
  const el = document.activeElement;
  if (el?.matches('input,textarea,select') && (el.closest('#inspector form') || el.id === 'project-name' || el.dataset.phase !== undefined)) {
    if (!el.reportValidity()) return false;
    el.blur();
  }
  return true;
}
function serializeHTML(snapshot) {
  const clone = document.documentElement.cloneNode(true);
  clone.querySelector('#saved-project').textContent = JSON.stringify(snapshot).replace(/</g, '\\u003c');
  clone.querySelector('title').textContent = snapshot.name + ' · Homelab';
  clone.querySelectorAll('dialog').forEach(d => d.removeAttribute('open'));
  clone.querySelector('#toast').classList.remove('visible');
  return '<!doctype html>\n' + clone.outerHTML;
}
async function saveTopology(chooseOther = false) {
  if (fileSave.busy || !fileSave.ready || !commitPendingEdits()) return;
  if (!fileSave.supported) {saveHTML(); return;}
  const key = fileTargetKey();
  fileSave.busy = true;
  fileSave.error = '';
  renderSaveState();
  let writable;
  try {
    let handle = chooseOther ? null : fileSave.handle;
    if (!handle) handle = await window.showSaveFilePicker({
      id: 'homelab-html', suggestedName: currentHtmlName(),
      types: [{description: '可编辑 Homelab HTML', accept: {'text/html': ['.html', '.htm']}}],
      excludeAcceptAllOption: true
    });
    assert(/\.html?$/i.test(handle.name), '请选择 HTML 文件');
    if (await handle.queryPermission({mode: 'readwrite'}) !== 'granted') {
      assert(await handle.requestPermission({mode: 'readwrite'}) === 'granted', '未获得文件写入权限，原文件未修改');
    }
    assert(key === fileTargetKey(), '拓扑已切换，请重新保存');
    persist();
    const snapshot = validate(project);
    const html = serializeHTML(snapshot);
    writable = await handle.createWritable();
    await writable.write(html);
    await writable.close();
    writable = null;
    if (key === fileTargetKey()) {
      fileSave.handle = handle;
      fileSave.savedContent = projectStamp(snapshot);
      fileSave.savedName = handle.name;
    }
    // Persist the handle, never request filesystem permission during page load.
    try {await fileTargetStore(key, handle);} catch {}
    toast(`已写入 ${handle.name}`);
  } catch (error) {
    if (writable) {try {await writable.abort();} catch {}}
    if (error.name === 'AbortError') toast('已取消保存');
    else {fileSave.error = error.message || '文件写入失败'; toast('未保存：' + fileSave.error);}
  } finally {
    fileSave.busy = false;
    renderSaveState();
  }
}
