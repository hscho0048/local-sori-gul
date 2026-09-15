// 소리글 dashboard. Single classic script (no imports/exports) — precompiled by scripts/build-tauri-assets.cjs.

const VIEWS = [
  ['all', '전체 보드'],
  ['starred', '중요 보드'],
  ['live', '미완료 녹음'],
  ['trash', '휴지통'],
];

const COLUMNS = [
  ['title', '보드 이름'],
  ['duration', '길이'],
  ['folder', '폴더 위치'],
  ['created', '생성일'],
];

const formatDuration = (seconds) => {
  if (seconds == null) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
};

const formatDate = (unixSeconds) => {
  const d = new Date(unixSeconds * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

// nulls last regardless of dir; string columns use localeCompare('ko'), numeric columns subtract.
const compareNotes = (a, b, sort) => {
  const dir = sort.dir === 'asc' ? 1 : -1;
  const av = sort.key === 'folder' ? a.folder : a[sort.key];
  const bv = sort.key === 'folder' ? b.folder : b[sort.key];
  if (av == null || bv == null) {
    if (av == null && bv == null) return 0;
    return av == null ? 1 : -1;
  }
  return typeof av === 'string' ? av.localeCompare(bv, 'ko') * dir : (av - bv) * dir;
};

const DEVICES = [['npu', 'NPU (Hexagon)'], ['gpu', 'GPU (Adreno)']];

const Chooser = ({ open, job, onClose, startPolling, openNote }) => {
  const [step, setStep] = React.useState('choose');
  const [device, setDevice] = React.useState('npu');
  const [mics, setMics] = React.useState(null); // null = not loaded yet
  const [mic, setMic] = React.useState('');
  const [errorMsg, setErrorMsg] = React.useState('');
  const dialogRef = React.useRef(null);
  const busy = job.state === 'running';

  React.useEffect(() => {
    if (!open) return;
    setStep('choose');
    setErrorMsg('');
    setMics(null);
    setMic('');
  }, [open]);

  // onClose is a fresh arrow function on every App render; reading it through a ref (instead of putting it
  // in the deps array below) keeps this effect from re-running — and re-stealing focus into the dialog —
  // on every unrelated App re-render (e.g. every 500ms poll tick) while the chooser is open.
  const onCloseRef = React.useRef(onClose);
  onCloseRef.current = onClose;

  // Focus the dialog once when it opens; Escape closes it (accessibility basics from the brief).
  // ponytail: no focus trap (Tab can leave the dialog) and no focus-return to the "+ 새 받아쓰기" button on
  // close. Fine for this single small modal; upgrade path is a small focus-trap util + remembering
  // document.activeElement before open and restoring it in onClose.
  React.useEffect(() => {
    if (!open) return undefined;
    if (dialogRef.current) dialogRef.current.focus();
    const onKeyDown = (e) => { if (e.key === 'Escape') onCloseRef.current(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  if (!open) return null;

  const pickFile = () => {
    setErrorMsg('');
    window.SoriBridge.pickAudio().then((path) => {
      if (!path) return;
      window.SoriBridge.transcribe(path, device).then(
        ({ note_id }) => { onClose(); startPolling(); openNote(note_id); },
        (err) => setErrorMsg(err.message || String(err)),
      );
    }, (err) => setErrorMsg(err.message || String(err)));
  };

  const goLive = () => {
    setErrorMsg('');
    setStep('mic');
    window.SoriBridge.mics().then(
      (list) => { setMics(list); setMic(list[0] ?? ''); }, // default to the first mic — with exactly one
                                                             // option <select>'s onChange never fires, so
                                                             // without this `mic` stays '' and /live 400s
      (err) => { setMics([]); setErrorMsg(err.message || String(err)); },
    );
  };

  const startRecording = () => {
    setErrorMsg('');
    window.SoriBridge.startLive(mic, device).then(
      ({ note_id }) => { onClose(); startPolling(); openNote(note_id); },
      (err) => setErrorMsg(err.message || String(err)),
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="새 받아쓰기"
        tabIndex={-1}
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="modal-title">새 받아쓰기</h2>
        <label className="modal-field">
          <span>연산 장치</span>
          <select value={device} onChange={(e) => setDevice(e.target.value)}>
            {DEVICES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
        </label>
        {step === 'choose' && (
          <div className="modal-actions">
            <button className="modal-choice" disabled={busy} onClick={pickFile}>오디오 전사…</button>
            <button className="modal-choice" disabled={busy} onClick={goLive}>실시간 전사</button>
          </div>
        )}
        {step === 'mic' && (
          <div className="modal-mic">
            {mics == null ? (
              <div className="modal-hint">마이크 목록을 불러오는 중…</div>
            ) : mics.length === 0 ? (
              <div className="modal-hint">사용할 수 있는 마이크를 찾지 못했습니다. 마이크를 연결하고 Windows 개인 정보 설정에서 마이크 접근을 허용해 주세요.</div>
            ) : (
              <select value={mic} onChange={(e) => setMic(e.target.value)}>
                {mics.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            )}
            <p className="modal-hint">말이 끊길 때마다 바로 전사해 본문에 이어 붙입니다. ⏹ 녹음 마치기로 끝내면 녹음 파일도 보관됩니다.</p>
            <button className="btn btn-primary" disabled={busy || !mics || mics.length === 0} onClick={startRecording}>녹음 시작</button>
          </div>
        )}
        {errorMsg && <div className="modal-error">{errorMsg}</div>}
      </div>
    </div>
  );
};

const countOccurrences = (text, sub) => {
  if (!sub) return 0;
  let count = 0;
  let idx = 0;
  for (;;) {
    idx = text.indexOf(sub, idx);
    if (idx === -1) return count;
    count += 1;
    idx += sub.length;
  }
};

const Editor = ({ noteId, job, chooserOpen, onClose }) => {
  const [title, setTitle] = React.useState('');
  const [transcript, setTranscript] = React.useState('');
  const [loaded, setLoaded] = React.useState(false); // false until note(id) has actually resolved once
  const [loadError, setLoadError] = React.useState('');
  const [saveStatus, setSaveStatus] = React.useState('');
  const [findOpen, setFindOpen] = React.useState(false);
  const [needle, setNeedle] = React.useState('');
  const [replacement, setReplacement] = React.useState('');
  const [findMsg, setFindMsg] = React.useState('');
  const [exportMsg, setExportMsg] = React.useState('');
  const textareaRef = React.useRef(null);
  const savedRef = React.useRef({ title: '', transcript: '' }); // last value persisted to the server
  const saveTimerRef = React.useRef(null);
  const findOpenRef = React.useRef(findOpen);
  findOpenRef.current = findOpen;
  const chooserOpenRef = React.useRef(chooserOpen);
  chooserOpenRef.current = chooserOpen;

  const jobRunningHere = job.state === 'running' && job.note_id === noteId;
  const jobRunningRef = React.useRef(jobRunningHere);
  jobRunningRef.current = jobRunningHere;

  const loadNote = React.useCallback(() => {
    window.SoriBridge.note(noteId).then(
      (n) => {
        setTitle(n.title);
        setTranscript(n.transcript || '');
        savedRef.current = { title: n.title, transcript: n.transcript || '' };
        setLoaded(true);
        setLoadError('');
      },
      (err) => setLoadError(err.message || String(err)),
    );
  }, [noteId]);

  React.useEffect(() => { loadNote(); }, [loadNote]);

  // Reload just the transcript once this note's own job finishes — the server has already written the
  // final text by the time state flips off 'running'. Deliberately NOT reloading title here: title
  // autosaves independently of the job (see flushSave), so re-fetching it too could stomp an edit made,
  // or just saved, while the job was running (item 3 fix — title used to always lose that race).
  const prevRunningRef = React.useRef(jobRunningHere);
  React.useEffect(() => {
    if (prevRunningRef.current && !jobRunningHere) {
      window.SoriBridge.note(noteId).then(
        (n) => {
          setTranscript(n.transcript || '');
          savedRef.current = { ...savedRef.current, transcript: n.transcript || '' };
        },
        (err) => setLoadError(err.message || String(err)),
      );
    }
    prevRunningRef.current = jobRunningHere;
  }, [jobRunningHere, noteId]);

  React.useEffect(() => {
    if (jobRunningHere && textareaRef.current) {
      textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
    }
  }, [jobRunningHere, job.text]);

  // Only the transcript field is ever gated on the job — it's the job's own output, and the server writes
  // it directly, so we must never PATCH over that. Title has no such owner and always autosaves, including
  // while our job is running. On failure we deliberately do NOT touch savedRef, so the edit stays "pending"
  // (the diff against savedRef is still there) and the next change or flush retries it.
  const flushSave = () => {
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    const fields = {};
    if (title !== savedRef.current.title) fields.title = title;
    if (!jobRunningRef.current && transcript !== savedRef.current.transcript) fields.transcript = transcript;
    if (Object.keys(fields).length === 0) return Promise.resolve();
    setSaveStatus('저장 중…');
    return window.SoriBridge.updateNote(noteId, fields).then(
      () => { savedRef.current = { ...savedRef.current, ...fields }; setSaveStatus('저장됨'); },
      (err) => {
        const msg = err.message || String(err);
        setSaveStatus(`저장하지 못했습니다: ${msg}`);
        throw err; // let callers (export, flush-on-close) know the save didn't actually land
      },
    );
  };
  const flushRef = React.useRef(flushSave);
  flushRef.current = flushSave;

  // Debounced autosave. Harmless no-op when title/transcript match savedRef (e.g. right after load), and
  // held off entirely until the note has actually loaded (so a slow/failed load can't let a stray edit
  // autosave a blank transcript over the real one).
  React.useEffect(() => {
    if (!loaded) return undefined;
    saveTimerRef.current = setTimeout(() => flushRef.current().catch(() => {}), 800);
    return () => clearTimeout(saveTimerRef.current);
  }, [title, transcript, loaded]);

  // Flush any pending edit when the editor closes/unmounts (covers both the explicit "← 목록" click below
  // and the <Editor key={openNoteId}> remount App does when switching straight to a different note).
  React.useEffect(() => () => { flushRef.current().catch(() => {}); }, []);

  React.useEffect(() => {
    const onKeyDown = (e) => {
      if (chooserOpenRef.current) return; // the chooser dialog owns Escape/Ctrl+H while it's open
      if (e.ctrlKey && (e.key === 'h' || e.key === 'H')) {
        e.preventDefault();
        setFindOpen((v) => !v);
      } else if (e.key === 'Escape' && findOpenRef.current) {
        setFindOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  React.useEffect(() => {
    if (!findOpen) return;
    setFindMsg('');
    const ta = textareaRef.current;
    if (ta) {
      const sel = ta.value.slice(ta.selectionStart, ta.selectionEnd);
      if (sel) setNeedle(sel);
    }
  }, [findOpen]);

  const findNext = () => {
    const ta = textareaRef.current;
    if (!ta || !needle) { setFindMsg('찾는 말이 없습니다.'); return false; }
    const text = ta.value;
    let idx = text.indexOf(needle, ta.selectionEnd);
    if (idx === -1) idx = text.indexOf(needle, 0);
    if (idx === -1) { setFindMsg('찾는 말이 없습니다.'); return false; }
    ta.focus();
    ta.setSelectionRange(idx, idx + needle.length);
    setFindMsg(`${countOccurrences(text, needle)}곳 있습니다.`);
    return true;
  };

  // Replaces ta's [start, end) with newText as a single, real undo step. execCommand('insertText') is the
  // way Chromium puts a programmatic textarea edit onto its native undo stack (so Ctrl+Z reverts it in one
  // go, as the find/replace messages promise); it also fires a trusted 'input' event itself, which is what
  // syncs `transcript` state back through the textarea's onChange. setRangeText + a manually dispatched
  // input event is kept only as a fallback for a WebView2 build where execCommand is unavailable/returns
  // false — that path doesn't get real undo, but the edit still lands and autosave still picks it up.
  const applyReplacement = (ta, start, end, newText) => {
    ta.focus();
    ta.setSelectionRange(start, end);
    let ok = false;
    try { ok = document.execCommand('insertText', false, newText); } catch (e) { ok = false; }
    if (!ok) {
      ta.setRangeText(newText, start, end, 'end');
      ta.dispatchEvent(new Event('input', { bubbles: true }));
    }
  };

  const replaceOne = () => {
    const ta = textareaRef.current;
    if (!ta || !needle) return;
    const selected = ta.value.slice(ta.selectionStart, ta.selectionEnd);
    if (selected === needle) applyReplacement(ta, ta.selectionStart, ta.selectionEnd, replacement);
    findNext();
  };

  const replaceAll = () => {
    const ta = textareaRef.current;
    if (!ta || !needle) return;
    const text = ta.value;
    const count = countOccurrences(text, needle);
    if (count === 0) { setFindMsg('찾는 말이 없습니다.'); return; }
    const newText = text.split(needle).join(replacement);
    applyReplacement(ta, 0, text.length, newText);
    setFindMsg(`${count}곳을 바꿨습니다. 되돌리려면 Ctrl+Z.`);
  };

  const exportTxt = () => {
    window.SoriBridge.pickSavePath(`${title}.txt`).then((path) => {
      if (!path) return;
      flushSave().then(
        () => {
          window.SoriBridge.exportNote(noteId, path).then(
            () => setExportMsg('TXT로 저장했습니다.'),
            (err) => setExportMsg(err.message || String(err)),
          );
        },
        (err) => setExportMsg(`저장하지 못해 내보내지 못했습니다: ${err.message || String(err)}`),
      );
    }, (err) => setExportMsg(err.message || String(err)));
  };

  return (
    <div className="editor">
      <div className="editor-header">
        {/* ponytail: fires the flush PATCH without awaiting it before onClose()'s refresh() GET, so on a
            slow save the list can briefly show the pre-edit title for one refresh cycle. Upgrade path:
            await flushSave() before calling onClose() (needs onClose to be async-aware). */}
        <button className="btn" onClick={() => { flushSave().catch(() => {}); onClose(); }}>← 목록</button>
        <input
          className="editor-title"
          value={title}
          disabled={!loaded}
          onChange={(e) => setTitle(e.target.value)}
        />
        <span className="save-status">{saveStatus}</span>
        <button className="btn" onClick={exportTxt}>TXT로 저장</button>
      </div>
      {loadError && <div className="modal-error">노트를 불러오지 못했습니다: {loadError}</div>}
      {exportMsg && <div className="editor-note">{exportMsg}</div>}
      {jobRunningHere && (
        <div className="job-status">
          {job.stage}{job.op === 'transcribe' ? ` · ${job.percent.toFixed(1)}%` : ''}
        </div>
      )}
      {findOpen && (
        <div className="find-panel">
          {jobRunningHere ? (
            <span className="modal-hint">전사 중에는 바꿀 수 없습니다.</span>
          ) : (
            <React.Fragment>
              <input
                className="find-input"
                placeholder="찾을 말"
                value={needle}
                onChange={(e) => setNeedle(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') findNext(); }}
              />
              <input
                className="find-input"
                placeholder="바꿀 말"
                value={replacement}
                onChange={(e) => setReplacement(e.target.value)}
              />
              <button className="btn" onClick={findNext}>다음 찾기</button>
              <button className="btn" onClick={replaceOne}>바꾸기</button>
              <button className="btn" onClick={replaceAll}>모두 바꾸기</button>
              {findMsg && <span className="find-msg">{findMsg}</span>}
            </React.Fragment>
          )}
        </div>
      )}
      <textarea
        ref={textareaRef}
        className="editor-textarea"
        value={jobRunningHere ? job.text : transcript}
        readOnly={jobRunningHere || !loaded}
        onChange={(e) => setTranscript(e.target.value)}
      />
    </div>
  );
};

const LivePill = ({ job }) => {
  const isLive = job.state === 'running' && job.op === 'listen';
  const startRef = React.useRef(null);
  const [stopping, setStopping] = React.useState(false);
  const [, setTick] = React.useState(0);

  React.useEffect(() => {
    if (isLive) {
      if (startRef.current == null) startRef.current = Date.now(); // first poll that saw it running
    } else {
      startRef.current = null;
      setStopping(false);
    }
  }, [isLive]);

  React.useEffect(() => {
    if (!isLive) return undefined;
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [isLive]);

  if (!isLive) return null;

  const elapsed = startRef.current ? Math.floor((Date.now() - startRef.current) / 1000) : 0;
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  const onStop = () => {
    setStopping(true);
    window.SoriBridge.stopLive().catch(() => setStopping(false));
  };

  return (
    <div className="live-pill">
      <span className="live-dot" aria-hidden="true" />
      <span className="live-time">{m}:{String(s).padStart(2, '0')}</span>
      <span className="live-stage">{job.stage}</span>
      {stopping ? (
        <span className="live-stopping">마지막 구간 전사 중…</span>
      ) : (
        <button className="live-stop" onClick={onStop}>⏹ 녹음 마치기</button>
      )}
    </div>
  );
};

const TopBar = ({ query, setQuery, folders, folderFilter, setFolderFilter, onNewNote }) => {
  const [filterOpen, setFilterOpen] = React.useState(false);
  const activeFolder = folders.find((f) => f.id === folderFilter);
  return (
    <header className="topbar">
      <div className="brand">소리글</div>
      <input
        className="search"
        placeholder="검색어를 입력해 주세요"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="dropdown">
        <button className="btn" onClick={() => setFilterOpen((v) => !v)}>
          {activeFolder ? `필터 · ${activeFolder.name}` : '필터'}
        </button>
        {filterOpen && (
          <div className="dropdown-menu">
            <button className="dropdown-item" onClick={() => { setFolderFilter(null); setFilterOpen(false); }}>모든 폴더</button>
            {folders.map((f) => (
              <button key={f.id} className="dropdown-item" onClick={() => { setFolderFilter(f.id); setFilterOpen(false); }}>{f.name}</button>
            ))}
          </div>
        )}
      </div>
      <button className="btn btn-primary" onClick={onNewNote}>+ 새 받아쓰기</button>
      <button className="icon-btn" aria-label="알림" disabled>🔔</button>
      <button className="icon-btn" aria-label="도움말" title="Ctrl+H: 찾아 바꾸기" disabled>?</button>
    </header>
  );
};

const Sidebar = ({ view, setView, liveCount, folders, onCreateFolder, onDeleteFolder, collapsed, setCollapsed }) => {
  const [addingFolder, setAddingFolder] = React.useState(false);
  const [folderName, setFolderName] = React.useState('');

  const submitFolder = () => {
    const name = folderName.trim();
    if (name) onCreateFolder(name);
    setAddingFolder(false);
    setFolderName('');
  };

  return (
    <nav className="sidebar">
      {!collapsed && <div className="sidebar-label">내 받아쓰기</div>}
      {VIEWS.map(([key, label]) => (
        <button key={key} className={`nav-item${view === key ? ' active' : ''}`} onClick={() => setView(key)}>
          <span>{collapsed ? label[0] : label}</span>
          {key === 'live' && liveCount > 0 && <span className="badge">{liveCount}</span>}
        </button>
      ))}
      <div className="sidebar-row">
        {!collapsed && <div className="sidebar-label">폴더</div>}
        <button className="icon-btn" aria-label="폴더 추가" onClick={() => setAddingFolder(true)}>+</button>
      </div>
      {addingFolder && (
        <input
          autoFocus
          className="folder-input"
          value={folderName}
          onChange={(e) => setFolderName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitFolder();
            else if (e.key === 'Escape') { setAddingFolder(false); setFolderName(''); }
          }}
          onBlur={() => { if (folderName.trim() === '') { setAddingFolder(false); setFolderName(''); } else submitFolder(); }}
        />
      )}
      {folders.map((f) => (
        <div key={f.id} className="folder-item">
          <button className={`nav-item${view === `folder:${f.id}` ? ' active' : ''}`} onClick={() => setView(`folder:${f.id}`)}>
            {collapsed ? f.name[0] : f.name}
          </button>
          {!collapsed && (
            <button className="folder-delete" aria-label="폴더 삭제" onClick={() => onDeleteFolder(f.id)}>×</button>
          )}
        </div>
      ))}
      <button className="collapse-btn" aria-label="사이드바 접기" onClick={() => setCollapsed((v) => !v)}>
        {collapsed ? '»' : '«'}
      </button>
    </nav>
  );
};

const Row = ({ note, selected, onToggleSelect, onOpen, job }) => {
  const isRunning = job && job.state === 'running' && job.note_id === note.id;
  const interrupted = note.source === 'live' && !isRunning;
  return (
    <tr className="row" onClick={() => onOpen(note.id)}>
      <td className="col-check" onClick={(e) => e.stopPropagation()}>
        <input type="checkbox" checked={selected} onChange={() => onToggleSelect(note.id)} aria-label={`${note.title} 선택`} />
      </td>
      <td className="col-title">
        <div className="title-line">
          {note.starred ? <span className="star" aria-hidden="true">★</span> : null}
          <span className="title">{note.title}</span>
          {interrupted && <span className="chip chip-danger">녹음 중단됨</span>}
        </div>
        {note.keywords && note.keywords.length > 0 && (
          <div className="keywords">
            {note.keywords.map((k, i) => <span key={`${k}-${i}`} className="chip">{k}</span>)}
          </div>
        )}
      </td>
      <td>{formatDuration(note.duration)}</td>
      <td>{note.folder || '—'}</td>
      <td>{formatDate(note.created)}</td>
    </tr>
  );
};

const Table = ({ notes, view, sort, onSort, selection, onToggleSelect, onToggleSelectAll, onOpen, job }) => {
  const allIds = notes.map((n) => n.id);
  const allSelected = allIds.length > 0 && allIds.every((id) => selection.has(id));
  const emptyText = view === 'trash' ? '휴지통이 비어 있습니다.' : '받아쓰기가 없습니다.';

  return (
    <table className="table">
      <thead>
        <tr>
          <th className="col-check">
            <input type="checkbox" checked={allSelected} onChange={() => onToggleSelectAll(allIds)} aria-label="전체 선택" />
          </th>
          {COLUMNS.map(([key, label]) => (
            <th key={key}>
              <button className="sort-btn" onClick={() => onSort(key)}>
                {label} {sort.key === key ? (sort.dir === 'asc' ? '▲' : '▼') : ''}
              </button>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {notes.length === 0 && <tr><td className="empty" colSpan={5}>{emptyText}</td></tr>}
        {notes.map((note) => (
          <Row key={note.id} note={note} selected={selection.has(note.id)} onToggleSelect={onToggleSelect} onOpen={onOpen} job={job} />
        ))}
      </tbody>
    </table>
  );
};

const ActionBar = ({ count, view, folders, onToggleStar, onMoveFolder, onTrash, onRestore, onDeleteForever, onClear }) => (
  <div className="action-bar">
    <span>{count}개 선택</span>
    {view === 'trash' ? (
      <React.Fragment>
        <button className="btn" onClick={onRestore}>복원</button>
        <button className="btn btn-danger" onClick={onDeleteForever}>영구 삭제</button>
      </React.Fragment>
    ) : (
      <React.Fragment>
        <button className="btn" onClick={onToggleStar}>중요</button>
        <select
          className="folder-select"
          aria-label="폴더 이동"
          defaultValue=""
          onChange={(e) => {
            const value = e.target.value;
            if (value === '') return;
            onMoveFolder(value === 'none' ? null : Number(value));
            e.target.value = '';
          }}
        >
          <option value="" disabled>폴더 이동</option>
          <option value="none">폴더 없음</option>
          {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <button className="btn" onClick={onTrash}>휴지통</button>
      </React.Fragment>
    )}
    <button className="btn" onClick={onClear}>선택 해제</button>
  </div>
);

const App = () => {
  const [view, setView] = React.useState('all');
  const [query, setQuery] = React.useState('');
  const [folderFilter, setFolderFilter] = React.useState(null);
  const [notes, setNotes] = React.useState([]);
  const [folders, setFolders] = React.useState([]);
  const [liveCount, setLiveCount] = React.useState(0);
  const [selection, setSelection] = React.useState(() => new Set());
  const [sort, setSort] = React.useState({ key: 'created', dir: 'desc' });
  const [openNoteId, setOpenNoteId] = React.useState(null);
  const [job, setJob] = React.useState({ state: 'idle' });
  const [chooserOpen, setChooserOpen] = React.useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false);
  const [error, setError] = React.useState('');

  // refresh() always reads the CURRENT view/query (via refs, not closure) and tags each request with a
  // sequence number, so a request started for a view/query that's no longer current can never overwrite
  // fresher state — whether it's still in flight or was sitting in a debounce timer that fired late.
  const viewRef = React.useRef(view);
  const queryRef = React.useRef(query);
  viewRef.current = view;
  queryRef.current = query;
  const requestSeq = React.useRef(0);

  const refresh = React.useCallback(() => {
    const seq = ++requestSeq.current;
    const v = viewRef.current;
    const q = queryRef.current;
    Promise.all([window.SoriBridge.notes(v, q), window.SoriBridge.folders(), window.SoriBridge.notes('live')]).then(
      ([n, f, live]) => {
        if (seq !== requestSeq.current) return;
        setNotes(n); setFolders(f); setLiveCount(live.length); setError('');
      },
      (err) => {
        if (seq !== requestSeq.current) return;
        setError(err.message || String(err));
      },
    );
  }, []);

  // Polls SoriBridge.job() while a job is running, stopping itself once it settles. Chained via setTimeout
  // (schedule-the-next-tick-only-after-the-response-lands) rather than setInterval, so a slow response can
  // never overlap the next request — a setInterval tick fires on the wall clock regardless of whether the
  // previous fetch is still in flight, so a late 'running' reply arriving after a later tick's 'done' reply
  // could win the race and freeze the UI showing 'running' forever.
  // awaitingFirstRef covers the "job fails before the first tick" gap: startPolling() is called right after
  // Chooser's transcribe()/startLive() succeeds, before React's `job` state has seen anything but the old
  // (often 'idle') value. If the job is already done/errored by the very first tick, `prev.state ===
  // 'running'` would be false and the done/error transition would be silently missed — awaitingFirstRef
  // makes that first tick count as a transition unconditionally whenever it isn't itself 'running'.
  const pollTimerRef = React.useRef(null);
  const pollingRef = React.useRef(false);
  const startPolling = () => {
    if (pollingRef.current) return; // already polling
    pollingRef.current = true;
    let awaitingFirst = true;
    const tick = () => {
      window.SoriBridge.job().then(
        (j) => {
          if (!pollingRef.current) return; // stopPolling() ran while this request was in flight
          const first = awaitingFirst;
          awaitingFirst = false;
          setJob((prev) => {
            if (j.state !== 'running' && (first || prev.state === 'running')) {
              refresh();
              if (j.state === 'error') setError(j.error || '작업이 실패했습니다.');
            }
            return j;
          });
          if (j.state === 'running') {
            pollTimerRef.current = setTimeout(tick, 500);
          } else {
            pollingRef.current = false;
            pollTimerRef.current = null;
          }
        },
        () => {
          awaitingFirst = false;
          if (pollingRef.current) pollTimerRef.current = setTimeout(tick, 500);
        },
      );
    };
    tick();
  };
  // Stop polling on unmount so an in-flight request's response can't setState after the App is gone.
  React.useEffect(() => () => {
    pollingRef.current = false;
    clearTimeout(pollTimerRef.current);
  }, []);

  const openNote = (id) => setOpenNoteId(id);

  // One effect for both: view changes refresh immediately (and clear selection); a query-only change
  // debounces. Because both live in one effect keyed on [view, query], a view change while a debounce
  // timer is pending re-runs the effect, which cancels that timer via the cleanup below before it can fire.
  const mountedRef = React.useRef(false);
  const prevViewRef = React.useRef(view);
  React.useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      prevViewRef.current = view;
      refresh();
      return undefined;
    }
    if (prevViewRef.current !== view) {
      prevViewRef.current = view;
      setSelection(new Set());
      refresh();
      return undefined;
    }
    const timer = setTimeout(refresh, 250);
    return () => clearTimeout(timer);
  }, [view, query]);
  // Seed job state once on mount; if the app was relaunched mid-job, that state is 'running' and we
  // start the interval so the LivePill/Editor pick it right back up.
  React.useEffect(() => {
    window.SoriBridge.job().then((j) => {
      setJob(j);
      if (j.state === 'running') startPolling();
    }, () => {});
  }, []);

  const visible = React.useMemo(() => {
    const filtered = folderFilter == null ? notes : notes.filter((n) => n.folder_id === folderFilter);
    return [...filtered].sort((a, b) => compareNotes(a, b, sort));
  }, [notes, folderFilter, sort]);

  const toggleSelect = (id) => setSelection((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const toggleSelectAll = (ids) => setSelection((prev) => {
    const allIn = ids.length > 0 && ids.every((id) => prev.has(id));
    return allIn ? new Set() : new Set(ids);
  });
  const toggleSort = (key) => setSort((prev) => (
    prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }
  ));

  const selectedNotes = notes.filter((n) => selection.has(n.id));
  // Policy: clear the selection and refresh() unconditionally, whether the bulk action fully succeeded,
  // partially succeeded, or failed outright — refresh() shows whatever actually landed on the server, and
  // any failure is surfaced in the error banner. (Chosen over "keep selection on total failure" for
  // simplicity: partial success already makes "was anything selected still valid" ambiguous.)
  const runBulk = (fn) => {
    const ids = Array.from(selection);
    Promise.allSettled(ids.map(fn)).then((results) => {
      setSelection(new Set());
      refresh();
      const failed = results.find((r) => r.status === 'rejected');
      if (failed) setError(failed.reason.message || String(failed.reason));
    });
  };
  const toggleStar = () => {
    const allStarred = selectedNotes.length > 0 && selectedNotes.every((n) => n.starred);
    runBulk((id) => window.SoriBridge.updateNote(id, { starred: !allStarred }));
  };
  const moveToFolder = (folderId) => runBulk((id) => window.SoriBridge.updateNote(id, { folder_id: folderId }));
  const trashSelected = () => runBulk((id) => window.SoriBridge.updateNote(id, { trashed: true }));
  const restoreSelected = () => runBulk((id) => window.SoriBridge.updateNote(id, { trashed: false }));
  const deleteSelected = () => {
    if (!window.confirm('선택한 받아쓰기를 영구 삭제할까요? 오디오도 지워집니다.')) return;
    runBulk((id) => window.SoriBridge.deleteNote(id));
  };

  const createFolder = (name) => window.SoriBridge.createFolder(name).then(refresh, (err) => setError(err.message || String(err)));
  const deleteFolderById = (id) => {
    if (!window.confirm('폴더를 삭제할까요? 받아쓰기는 남습니다.')) return;
    window.SoriBridge.deleteFolder(id).then(
      () => { if (view === `folder:${id}`) setView('all'); refresh(); },
      (err) => setError(err.message || String(err)),
    );
  };

  const findFolderName = (id) => {
    const f = folders.find((x) => x.id === id);
    return f ? f.name : '';
  };
  const heading = view.startsWith('folder:')
    ? findFolderName(Number(view.slice('folder:'.length)))
    : ((VIEWS.find(([key]) => key === view) || [])[1] || '');

  return (
    <div className={`app${sidebarCollapsed ? ' collapsed' : ''}`}>
      <TopBar
        query={query}
        setQuery={setQuery}
        folders={folders}
        folderFilter={folderFilter}
        setFolderFilter={setFolderFilter}
        onNewNote={() => setChooserOpen(true)}
      />
      <Sidebar
        view={view}
        setView={setView}
        liveCount={liveCount}
        folders={folders}
        onCreateFolder={createFolder}
        onDeleteFolder={deleteFolderById}
        collapsed={sidebarCollapsed}
        setCollapsed={setSidebarCollapsed}
      />
      <main className="main">
        {error && <div className="banner">{error}</div>}
        {openNoteId ? (
          // key={openNoteId}: remounts the editor when switching straight from one note to another (e.g.
          // clicking a different row while one is already open), instead of updating in place — so the old
          // note's local title/transcript state can never survive to be PATCHed onto the new note's id.
          // The remount's unmount-cleanup effect flushes the old note's pending save first (see Editor).
          <Editor
            key={openNoteId}
            noteId={openNoteId}
            job={job}
            chooserOpen={chooserOpen}
            onClose={() => { setOpenNoteId(null); refresh(); }}
          />
        ) : (
          <React.Fragment>
            <h1 className="heading">{heading}</h1>
            {selection.size > 0 && (
              <ActionBar
                count={selection.size}
                view={view}
                folders={folders}
                onToggleStar={toggleStar}
                onMoveFolder={moveToFolder}
                onTrash={trashSelected}
                onRestore={restoreSelected}
                onDeleteForever={deleteSelected}
                onClear={() => setSelection(new Set())}
              />
            )}
            <Table
              notes={visible}
              view={view}
              sort={sort}
              onSort={toggleSort}
              selection={selection}
              onToggleSelect={toggleSelect}
              onToggleSelectAll={toggleSelectAll}
              onOpen={openNote}
              job={job}
            />
          </React.Fragment>
        )}
      </main>
      <Chooser open={chooserOpen} job={job} onClose={() => setChooserOpen(false)} startPolling={startPolling} openNote={openNote} />
      <LivePill job={job} />
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
