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
    if (!response.ok) throw new Error(data.error || response.statusText);
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
    transcribe: (path, device) => call('POST', '/transcribe', { path, device }),
    startLive: (mic, device) => call('POST', '/live', { mic, device }),
    stopLive: () => call('POST', '/live/stop', {}),
    job: () => call('GET', '/job'),
    pickAudio: () => tauri.dialog.open({ multiple: false, directory: false, filters: [{ name: '오디오', extensions: AUDIO }] }),
    pickSavePath: (defaultName) => tauri.dialog.save({ defaultPath: defaultName, filters: [{ name: '텍스트 파일', extensions: ['txt'] }] }),
  });
})();
