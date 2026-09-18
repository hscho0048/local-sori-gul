(function () {
  const AUDIO = ['wav', 'mp3', 'm4a', 'flac', 'aac', 'ogg', 'opus', 'wma', 'mp4'];
  const tauri = window.__TAURI__;
  const ready = tauri.core.invoke('bridge').then(([url, token]) => ({ url, token }));

  const call = async (method, path, body) => {
    const { url, token } = await ready;
    const response = await fetch(url + path, {
      method,
      headers: body === undefined ? { 'X-Bridge-Token': token } : { 'X-Bridge-Token': token, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.error || response.statusText);
      error.status = response.status;
      error.code = data.code; // stable id for the messages the UI translates (busy, invalid_file, …)
      throw error;
    }
    return data;
  };
  const q = encodeURIComponent;

  window.SoriBridge = Object.freeze({
    notes: (view, query = '') => call('GET', `/notes?view=${q(view)}&q=${q(query)}`),
    note: (id) => call('GET', `/notes/${id}`),
    updateNote: (id, fields) => call('PATCH', `/notes/${id}`, fields),
    deleteNote: (id) => call('DELETE', `/notes/${id}`),
    exportNote: (id, path) => call('POST', `/notes/${id}/export`, { path }),
    folders: () => call('GET', '/folders'),
    createFolder: (name) => call('POST', '/folders', { name }),
    deleteFolder: (id) => call('DELETE', `/folders/${id}`),
    mics: () => call('GET', '/mics'),
    // folderId: the folder open in the sidebar, where the new note starts (null = no folder)
    transcribe: (path, device, speakers = true, folderId = null) => call('POST', '/transcribe', { path, device, speakers, folder_id: folderId }),
    devices: () => call('GET', '/devices'),
    setup: () => call('POST', '/setup', {}),
    cancelJob: () => call('POST', '/job/cancel', {}),
    startLive: (mic, device, source, folderId = null) => call('POST', '/live', { mic, device, source, folder_id: folderId }),
    stopLive: () => call('POST', '/live/stop', {}),
    job: () => call('GET', '/job'),
    pickAudio: (filterName) => tauri.dialog.open({ multiple: false, directory: false, filters: [{ name: filterName, extensions: AUDIO }] }),
    // Tauri's native drag & drop (paths, not File objects); type is enter | over | leave | drop.
    onDrag: (handler) => ['enter', 'over', 'leave', 'drop'].forEach((type) =>
      tauri.event.listen(`tauri://drag-${type}`, (event) => handler(type, event.payload || {}))),
    // Tray labels, tray tooltip and window title follow the recording state and the UI language.
    setRecording: (recording, lang) => tauri.core.invoke('set_recording', { recording, lang }).catch(() => {}),
    onToggleRecording: (handler) => tauri.event.listen('toggle-recording', handler),
    isAudio: (path) => AUDIO.includes(String(path).split('.').pop().toLowerCase()),
    pickSavePath: (defaultName, filterName) => tauri.dialog.save({ defaultPath: defaultName, filters: [{ name: filterName, extensions: ['txt'] }] }),
  });
})();
