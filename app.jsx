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

// Stubs — Task 6 replaces these definitions (Chooser modal, transcript Editor, live-recording pill).
const Chooser = () => null;
const Editor = () => null;
const LivePill = () => null;

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

  // ponytail: one-shot job fetch, not the 500ms interval loop — Task 6 wires real polling + stop-on-idle.
  const startPolling = () => { window.SoriBridge.job().then(setJob, () => {}); };

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
  React.useEffect(() => { startPolling(); }, []);

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
          <Editor noteId={openNoteId} job={job} onClose={() => { setOpenNoteId(null); refresh(); }} />
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
