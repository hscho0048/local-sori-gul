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
    transcribe: (path, device, speakers = true) => call('POST', '/transcribe', { path, device, speakers }),
    devices: () => call('GET', '/devices'),
    setup: () => call('POST', '/setup', {}),
    cancelJob: () => call('POST', '/job/cancel', {}),
    startLive: (mic, device, source) => call('POST', '/live', { mic, device, source }),
    stopLive: () => call('POST', '/live/stop', {}),
    job: () => call('GET', '/job'),
    pickAudio: () => tauri.dialog.open({ multiple: false, directory: false, filters: [{ name: '오디오', extensions: AUDIO }] }),
    // Tauri's native drag & drop (paths, not File objects); type is enter | over | leave | drop.
    onDrag: (handler) => ['enter', 'over', 'leave', 'drop'].forEach((type) =>
      tauri.event.listen(`tauri://drag-${type}`, (event) => handler(type, event.payload || {}))),
    setRecording: (recording) => tauri.core.invoke('set_recording', { recording }).catch(() => {}),
    onToggleRecording: (handler) => tauri.event.listen('toggle-recording', handler),
    isAudio: (path) => AUDIO.includes(String(path).split('.').pop().toLowerCase()),
    pickSavePath: (defaultName) => tauri.dialog.save({ defaultPath: defaultName, filters: [{ name: '텍스트 파일', extensions: ['txt'] }] }),
  });
})();
