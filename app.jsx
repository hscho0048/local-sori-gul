// 소리글 dashboard. Single classic script (no imports/exports) — precompiled by scripts/build-tauri-assets.cjs.

// Every user-visible string, per language. `{name}` placeholders are filled by t(key, vars).
const STRINGS = {
  ko: {
    brand: '소리글', search: '검색어를 입력해 주세요', filter: '필터', 'filter.active': '필터 · {name}', 'filter.all': '모든 폴더',
    newNote: '+ 새 받아쓰기', details: '자세히', language: '언어',
    'view.all': '전체 보드', 'view.starred': '중요 보드', 'view.live': '미완료 녹음', 'view.trash': '휴지통',
    'col.title': '보드 이름', 'col.duration': '길이', 'col.folder': '폴더 위치', 'col.created': '생성일',
    'sidebar.mine': '내 받아쓰기', 'sidebar.folders': '폴더', 'sidebar.collapse': '사이드바 접기', 'sidebar.expand': '사이드바 펼치기',
    'folder.add': '폴더 추가', 'folder.delete': '폴더 삭제',
    'row.interrupted': '녹음 중단됨', 'row.select': '{title} 선택',
    'table.empty': '받아쓰기가 없습니다.', 'table.trashEmpty': '휴지통이 비어 있습니다.', 'table.selectAll': '전체 선택',
    'action.count': '{n}개 선택', 'action.restore': '복원', 'action.deleteForever': '영구 삭제', 'action.star': '중요',
    'action.move': '폴더 이동', 'action.noFolder': '폴더 없음', 'action.trash': '휴지통', 'action.clear': '선택 해제',
    'confirm.deleteNotes': '선택한 받아쓰기를 영구 삭제할까요? 오디오도 지워집니다.',
    'confirm.deleteFolder': '폴더를 삭제할까요? 받아쓰기는 남습니다.',
    'caption.min': '최소화', 'caption.max': '최대화', 'caption.restore': '이전 크기로', 'caption.close': '닫기',
    'drop.hint': '오디오 파일을 여기에 끌어 놓으세요',
    'device.npu': 'NPU (Hexagon)', 'device.gpu': 'GPU (Adreno)', 'device.intel-gpu': '인텔 GPU (OpenVINO)',
    'device.intel-npu': '인텔 NPU (OpenVINO)', 'device.cpu': 'CPU',
    'source.mic': '마이크', 'source.system': '시스템 소리 (Zoom·Teams)', 'source.both': '마이크 + 시스템 소리',
    'chooser.title': '새 받아쓰기', 'chooser.device': '연산 장치', 'chooser.speakers': '화자 분리',
    'chooser.file': '오디오 전사…', 'chooser.live': '실시간 전사', 'chooser.input': '소리 입력',
    'chooser.micsLoading': '마이크 목록을 불러오는 중…',
    'chooser.noMics': '사용할 수 있는 마이크를 찾지 못했습니다. 마이크를 연결하고 Windows 개인 정보 설정에서 마이크 접근을 허용해 주세요.',
    'chooser.systemHint': '회의 앱 소리를 그대로 받아씁니다. 스피커 볼륨과 관계없이 기록됩니다.',
    'chooser.liveHint': '말이 끊길 때마다 바로 전사해 본문에 이어 붙입니다. ⏹ 녹음 마치기로 끝내면 녹음 파일도 보관됩니다.',
    'chooser.start': '녹음 시작', 'filter.audio': '오디오', 'filter.txt': '텍스트 파일',
    cancel: '취소', cancelling: '취소 중…',
    'editor.back': '← 목록', 'editor.export': 'TXT로 저장', 'editor.saving': '저장 중…', 'editor.saved': '저장됨',
    'editor.saveFailed': '저장하지 못했습니다: {msg}', 'editor.loadFailed': '노트를 불러오지 못했습니다: {msg}',
    'export.done': 'TXT로 저장했습니다.', 'export.saveFailed': '저장하지 못해 내보내지 못했습니다: {msg}',
    'find.locked': '전사 중에는 바꿀 수 없습니다.', 'find.needle': '찾을 말', 'find.replacement': '바꿀 말',
    'find.next': '다음 찾기', 'find.replace': '바꾸기', 'find.replaceAll': '모두 바꾸기',
    'find.none': '찾는 말이 없습니다.', 'find.count': '{n}곳 있습니다.', 'find.replaced': '{n}곳을 바꿨습니다. 되돌리려면 Ctrl+Z.',
    'phase.loading': '준비 중…', 'phase.decoding': '오디오 읽는 중…', 'phase.diarizing': '화자 나누는 중…',
    'phase.transcribing': '받아쓰는 중 · {p}%', 'job.queued': '전사 대기 중', 'job.queueCount': '대기 {n}개',
    'live.recording': '녹음 중 · {source}', 'live.busy': '받아쓰는 중', 'live.finishing': '마지막 부분 받아쓰는 중…',
    'live.stop': '녹음 마치기',
    'live.source.mic': '마이크', 'live.source.system': '시스템 소리', 'live.source.both': '마이크 + 시스템 소리',
    'setup.speech': '음성 인식 모델', 'setup.speech.hint': '한국어를 받아쓰는 인공지능 모델',
    'setup.speaker': '화자 구분 모델', 'setup.speaker.hint': '누가 말했는지 나누는 모델',
    'setup.audio': '오디오 변환 도구', 'setup.audio.hint': '여러 형식의 오디오 파일을 읽는 도구',
    'setup.title': '소리글을 준비하고 있어요', 'setup.titleFailed': '준비를 마치지 못했어요',
    'setup.lead': '처음 한 번만 받아쓰기에 필요한 모델을 내려받아요{size}. 모델은 이 PC에만 저장되고, 그다음부터는 인터넷 없이 받아쓸 수 있어요.',
    'setup.size': ' (약 {size})',
    'setup.state.done': ' 완료', 'setup.state.active': ' 진행 중', 'setup.state.failed': ' 실패', 'setup.state.pending': ' 대기',
    'setup.converting': '이 PC에 맞게 모델을 준비하는 중…', 'setup.checking': '받아 둔 파일을 확인하는 중…',
    'setup.errorHelp': '인터넷 연결을 확인한 뒤 다시 시도해 주세요. 받던 파일은 이어서 받아요.',
    'setup.foot': '창을 닫아도 괜찮아요. 다음에 열면 이어서 받아요.', 'setup.retry': '다시 시도', 'setup.start': '내려받기 시작',
    'err.busy': '다른 전사 작업이 진행 중입니다. 끝난 뒤 다시 시작해 주세요.',
    'err.invalid_file': '지원하는 로컬 오디오 파일을 선택해 주세요.', 'err.no_mic': '마이크를 선택해 주세요.',
    'err.shutting_down': '앱을 종료하는 중입니다.', 'err.cancelled': '취소됐습니다.',
    'err.generic': '문제가 생겼습니다.', 'err.jobFailed': '작업이 실패했습니다.',
    'err.audioOnly': '오디오 파일만 전사할 수 있습니다.', 'err.noMicFound': '사용할 수 있는 마이크를 찾지 못했습니다.',
    'err.file': '{name}: {msg}',
  },
  en: {
    brand: 'Sorigul', search: 'Search', filter: 'Filter', 'filter.active': 'Filter · {name}', 'filter.all': 'All folders',
    newNote: '+ New transcription', details: 'Details', language: 'Language',
    'view.all': 'All', 'view.starred': 'Starred', 'view.live': 'Unfinished recordings', 'view.trash': 'Trash',
    'col.title': 'Name', 'col.duration': 'Length', 'col.folder': 'Folder', 'col.created': 'Created',
    'sidebar.mine': 'My transcripts', 'sidebar.folders': 'Folders', 'sidebar.collapse': 'Collapse sidebar', 'sidebar.expand': 'Expand sidebar',
    'folder.add': 'Add folder', 'folder.delete': 'Delete folder',
    'row.interrupted': 'Recording interrupted', 'row.select': 'Select {title}',
    'table.empty': 'No transcripts yet.', 'table.trashEmpty': 'Trash is empty.', 'table.selectAll': 'Select all',
    'action.count': '{n} selected', 'action.restore': 'Restore', 'action.deleteForever': 'Delete forever', 'action.star': 'Star',
    'action.move': 'Move to folder', 'action.noFolder': 'No folder', 'action.trash': 'Move to trash', 'action.clear': 'Deselect',
    'confirm.deleteNotes': 'Delete the selected transcripts forever? Their audio is deleted too.',
    'confirm.deleteFolder': 'Delete this folder? Its transcripts are kept.',
    'caption.min': 'Minimize', 'caption.max': 'Maximize', 'caption.restore': 'Restore', 'caption.close': 'Close',
    'drop.hint': 'Drop audio files here',
    'device.npu': 'NPU (Hexagon)', 'device.gpu': 'GPU (Adreno)', 'device.intel-gpu': 'Intel GPU (OpenVINO)',
    'device.intel-npu': 'Intel NPU (OpenVINO)', 'device.cpu': 'CPU',
    'source.mic': 'Microphone', 'source.system': 'System audio (Zoom·Teams)', 'source.both': 'Microphone + system audio',
    'chooser.title': 'New transcription', 'chooser.device': 'Processor', 'chooser.speakers': 'Speaker labels',
    'chooser.file': 'Transcribe audio…', 'chooser.live': 'Live transcription', 'chooser.input': 'Input',
    'chooser.micsLoading': 'Looking for microphones…',
    'chooser.noMics': 'No microphone found. Connect one and allow microphone access in Windows privacy settings.',
    'chooser.systemHint': 'Transcribes what your meeting app plays, whatever the speaker volume.',
    'chooser.liveHint': 'Each pause is transcribed right away and added to the text. Stop recording to keep the audio file too.',
    'chooser.start': 'Start recording', 'filter.audio': 'Audio', 'filter.txt': 'Text file',
    cancel: 'Cancel', cancelling: 'Cancelling…',
    'editor.back': '← List', 'editor.export': 'Save as TXT', 'editor.saving': 'Saving…', 'editor.saved': 'Saved',
    'editor.saveFailed': 'Couldn’t save: {msg}', 'editor.loadFailed': 'Couldn’t open this transcript: {msg}',
    'export.done': 'Saved as TXT.', 'export.saveFailed': 'Couldn’t save, so nothing was exported: {msg}',
    'find.locked': 'You can’t replace text while transcribing.', 'find.needle': 'Find', 'find.replacement': 'Replace with',
    'find.next': 'Find next', 'find.replace': 'Replace', 'find.replaceAll': 'Replace all',
    'find.none': 'No matches.', 'find.count': '{n} found.', 'find.replaced': 'Replaced {n}. Press Ctrl+Z to undo.',
    'phase.loading': 'Getting ready…', 'phase.decoding': 'Reading audio…', 'phase.diarizing': 'Finding speakers…',
    'phase.transcribing': 'Transcribing · {p}%', 'job.queued': 'Waiting to transcribe', 'job.queueCount': '{n} waiting',
    'live.recording': 'Recording · {source}', 'live.busy': 'Transcribing', 'live.finishing': 'Transcribing the last part…',
    'live.stop': 'Stop recording',
    'live.source.mic': 'Microphone', 'live.source.system': 'System audio', 'live.source.both': 'Microphone + system audio',
    'setup.speech': 'Speech recognition model', 'setup.speech.hint': 'The AI model that transcribes Korean',
    'setup.speaker': 'Speaker model', 'setup.speaker.hint': 'Tells who said what',
    'setup.audio': 'Audio converter', 'setup.audio.hint': 'Reads audio files in many formats',
    'setup.title': 'Setting up Sorigul', 'setup.titleFailed': 'Setup didn’t finish',
    'setup.lead': 'Sorigul downloads its models once{size}. They stay on this PC, and after that transcription works offline.',
    'setup.size': ' (about {size})',
    'setup.state.done': ' done', 'setup.state.active': ' in progress', 'setup.state.failed': ' failed', 'setup.state.pending': ' waiting',
    'setup.converting': 'Preparing the model for this PC…', 'setup.checking': 'Checking downloaded files…',
    'setup.errorHelp': 'Check your internet connection and try again. Downloads pick up where they stopped.',
    'setup.foot': 'You can close the window. The download resumes next time.', 'setup.retry': 'Try again', 'setup.start': 'Start download',
    'err.busy': 'Another transcription is running. Try again when it finishes.',
    'err.invalid_file': 'Choose a supported audio file on this PC.', 'err.no_mic': 'Choose a microphone.',
    'err.shutting_down': 'Sorigul is closing.', 'err.cancelled': 'Cancelled.',
    'err.generic': 'Something went wrong.', 'err.jobFailed': 'The task failed.',
    'err.audioOnly': 'Only audio files can be transcribed.', 'err.noMicFound': 'No microphone found.',
    'err.file': '{name}: {msg}',
  },
};
const savedLang = () => { try { return localStorage.getItem('sori.lang'); } catch (e) { return null; } };
// ponytail: the language is a module variable that t() reads; App keeps a copy in state only to re-render every component
// on a switch. Fine while nothing memoizes; pass it through context if a React.memo component ever shows stale text.
let uiLang = STRINGS[savedLang()] ? savedLang() : (/^ko/i.test(navigator.language || '') ? 'ko' : 'en');
document.documentElement.lang = uiLang;
const t = (key, vars) => String(STRINGS[uiLang][key] ?? STRINGS.ko[key] ?? key)
  .replace(/\{(\w+)\}/g, (_, name) => (vars && vars[name] != null ? vars[name] : ''));

// A message shown to the user, kept as data so it re-words on a language switch: { key?, vars?, error? }.
// Server errors carry a stable `code`; known codes are translated, the raw (Korean) text goes under Details.
const rawError = (error) => (error ? error.message || String(error) : '');
const say = (m) => {
  const raw = rawError(m.error);
  const code = m.error && m.error.code;
  const reason = code && STRINGS.ko[`err.${code}`] ? t(`err.${code}`) : (uiLang === 'ko' || !raw ? raw : t('err.generic'));
  const text = m.key ? t(m.key, { ...m.vars, msg: reason }) : reason;
  return [text, raw && !text.includes(raw) ? raw : ''];
};
const Msg = ({ m }) => {
  if (!m) return null;
  const [text, detail] = say(m);
  return (
    <React.Fragment>
      {text}
      {detail && <details className="msg-details"><summary>{t('details')}</summary><pre>{detail}</pre></details>}
    </React.Fragment>
  );
};
const deviceLabel = (d) => STRINGS[uiLang][`device.${d.id}`] || d.label;

const LangToggle = ({ lang, onChange }) => (
  <div className="lang-toggle" role="group" aria-label={t('language')}>
    {[['ko', '한'], ['en', 'EN']].map(([value, label]) => (
      <button key={value} type="button" aria-pressed={lang === value} lang={value} onClick={() => onChange(value)}>{label}</button>
    ))}
  </div>
);

const VIEWS = ['all', 'starred', 'live', 'trash'];
const COLUMNS = ['title', 'duration', 'folder', 'created'];

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

const SOURCES = ['mic', 'system', 'both'];
// Last live-recording choice, reused by the chooser and by Ctrl+Shift+R / the tray.
const loadLive = () => { try { return JSON.parse(localStorage.getItem('sori.live')) || {}; } catch (e) { return {}; } };
const saveLive = (value) => { try { localStorage.setItem('sori.live', JSON.stringify({ ...loadLive(), ...value })); } catch (e) { /* private mode: not remembered */ } };
const pickDevice = (devices, wanted) => (devices.some((d) => d.id === wanted) ? wanted : (devices[0] ? devices[0].id : ''));

const Chooser = ({ open, job, devices, onClose, startPolling, openNote }) => {
  const [step, setStep] = React.useState('choose');
  const [device, setDevice] = React.useState('');
  const [source, setSource] = React.useState('mic');
  const [speakers, setSpeakers] = React.useState(true);
  const [mics, setMics] = React.useState(null); // null = not loaded yet
  const [mic, setMic] = React.useState('');
  const [errorMsg, setErrorMsg] = React.useState(null);
  const dialogRef = React.useRef(null);
  const busy = job.state === 'running';
  const fail = (error) => setErrorMsg({ error });

  React.useEffect(() => {
    if (!open) return;
    setStep('choose');
    setErrorMsg(null);
    setMics(null);
    setMic('');
    setSource(loadLive().source || 'mic');
    setSpeakers(loadLive().speakers !== false);
  }, [open]);

  // Devices arrive from GET /devices (possibly after the chooser opened); keep the current pick if it's still
  // offered, else the remembered one, else the first probed device.
  React.useEffect(() => {
    if (open && devices) setDevice((current) => pickDevice(devices, current || loadLive().device));
  }, [open, devices]);

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
    setErrorMsg(null);
    window.SoriBridge.pickAudio(t('filter.audio')).then((path) => {
      if (!path) return;
      saveLive({ device, speakers });
      window.SoriBridge.transcribe(path, device, speakers).then(
        ({ note_id }) => { onClose(); startPolling(); openNote(note_id); },
        fail,
      );
    }, fail);
  };

  const goLive = () => {
    setErrorMsg(null);
    setStep('mic');
    window.SoriBridge.mics().then(
      (list) => { setMics(list); const saved = loadLive().mic; setMic(list.includes(saved) ? saved : (list[0] ?? '')); }, // default to the first mic — with exactly one
                                                             // option <select>'s onChange never fires, so
                                                             // without this `mic` stays '' and /live 400s
      (err) => { setMics([]); fail(err); },
    );
  };

  const startRecording = () => {
    setErrorMsg(null);
    saveLive({ device, mic, source });
    window.SoriBridge.startLive(source === 'system' ? '' : mic, device, source).then(
      ({ note_id }) => { onClose(); startPolling(); openNote(note_id); },
      fail,
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={t('chooser.title')}
        tabIndex={-1}
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="modal-title">{t('chooser.title')}</h2>
        <label className="modal-field">
          <span>{t('chooser.device')}</span>
          <select value={device} disabled={!devices} onChange={(e) => setDevice(e.target.value)}>
            {(devices || []).map((d) => <option key={d.id} value={d.id}>{deviceLabel(d)}</option>)}
          </select>
        </label>
        {step === 'choose' && (
          <React.Fragment>
            <label className="modal-check">
              <input type="checkbox" checked={speakers} onChange={(e) => setSpeakers(e.target.checked)} />
              <span>{t('chooser.speakers')}</span>
            </label>
            <div className="modal-actions">
              <button className="modal-choice" disabled={busy || !device} onClick={pickFile}>{t('chooser.file')}</button>
              <button className="modal-choice" disabled={busy || !device} onClick={goLive}>{t('chooser.live')}</button>
            </div>
          </React.Fragment>
        )}
        {step === 'mic' && (
          <div className="modal-mic">
            <label className="modal-field">
              <span>{t('chooser.input')}</span>
              <select value={source} onChange={(e) => setSource(e.target.value)}>
                {SOURCES.map((v) => <option key={v} value={v}>{t(`source.${v}`)}</option>)}
              </select>
            </label>
            {source !== 'system' && (mics == null ? (
              <div className="modal-hint">{t('chooser.micsLoading')}</div>
            ) : mics.length === 0 ? (
              <div className="modal-hint">{t('chooser.noMics')}</div>
            ) : (
              <select value={mic} onChange={(e) => setMic(e.target.value)}>
                {mics.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            ))}
            {source !== 'mic' && <p className="modal-hint">{t('chooser.systemHint')}</p>}
            <p className="modal-hint">{t('chooser.liveHint')}</p>
            <button className="btn btn-primary" disabled={busy || !device || (source !== 'system' && (!mics || mics.length === 0))} onClick={startRecording}>{t('chooser.start')}</button>
          </div>
        )}
        {errorMsg && <div className="modal-error"><Msg m={errorMsg} /></div>}
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

// Stays "취소 중…" until the job actually ends (the pill/status unmounts); only a failed request re-enables it.
const CancelButton = () => {
  const [busy, setBusy] = React.useState(false);
  return (
    <button className="btn-cancel" disabled={busy} onClick={() => { setBusy(true); window.SoriBridge.cancelJob().catch(() => setBusy(false)); }}>
      {busy ? t('cancelling') : t('cancel')}
    </button>
  );
};

// File-transcription status in user words, from the job's structured phase (never its Korean `stage`).
const fileStatus = (job) => (job.phase === 'transcribing'
  ? t('phase.transcribing', { p: Math.floor(job.percent || 0) })
  : t(['decoding', 'diarizing'].includes(job.phase) ? `phase.${job.phase}` : 'phase.loading'));

const Editor = ({ noteId, job, chooserOpen, onClose, onSaveError }) => {
  const [title, setTitle] = React.useState('');
  const [transcript, setTranscript] = React.useState('');
  const [loaded, setLoaded] = React.useState(false); // false until note(id) has actually resolved once
  const [loadError, setLoadError] = React.useState(null);
  // True from the moment the post-job transcript reload starts until it succeeds. Kept true forever on
  // failure (rather than unlocking back to the stale local `transcript`) — the point is that nobody may
  // edit/autosave over the server's just-written final transcript until we've actually confirmed what it is.
  const [reloadingTranscript, setReloadingTranscript] = React.useState(false);
  const reloadingRef = React.useRef(reloadingTranscript);
  reloadingRef.current = reloadingTranscript;
  const [saveStatus, setSaveStatus] = React.useState(null);
  const [findOpen, setFindOpen] = React.useState(false);
  const [needle, setNeedle] = React.useState('');
  const [replacement, setReplacement] = React.useState('');
  const [findMsg, setFindMsg] = React.useState(null);
  const [exportMsg, setExportMsg] = React.useState(null);
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
        setLoadError(null);
      },
      (error) => setLoadError({ key: 'editor.loadFailed', error }),
    );
  }, [noteId]);

  React.useEffect(() => { loadNote(); }, [loadNote]);

  // Reload just the transcript once this note's own job finishes — the server has already written the
  // final text by the time state flips off 'running'. Deliberately NOT reloading title here: title
  // autosaves independently of the job (see flushSave), so re-fetching it too could stomp an edit made,
  // or just saved, while the job was running (item 3 fix — title used to always lose that race).
  // reloadingTranscript keeps the textarea readOnly and the transcript field out of flushSave for the
  // whole span between "job stopped" and "we actually know the real transcript" — jobRunningHere already
  // flips to false the instant the job ends, and without this the textarea would briefly (or, on a failed
  // reload, permanently) show as an editable, autosave-eligible field still holding the pre-job local
  // `transcript` value, which could then get PATCHed over the server's real final text.
  const prevRunningRef = React.useRef(jobRunningHere);
  React.useEffect(() => {
    if (prevRunningRef.current && !jobRunningHere) {
      setReloadingTranscript(true);
      window.SoriBridge.note(noteId).then(
        (n) => {
          setTranscript(n.transcript || '');
          savedRef.current = { ...savedRef.current, transcript: n.transcript || '' };
          setReloadingTranscript(false);
        },
        (error) => setLoadError({ key: 'editor.loadFailed', error }), // stays locked: reloadingTranscript is not cleared
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
    const transcriptLocked = jobRunningRef.current || reloadingRef.current;
    if (!transcriptLocked && transcript !== savedRef.current.transcript) fields.transcript = transcript;
    if (Object.keys(fields).length === 0) return Promise.resolve();
    setSaveStatus({ key: 'editor.saving' });
    return window.SoriBridge.updateNote(noteId, fields).then(
      () => { savedRef.current = { ...savedRef.current, ...fields }; setSaveStatus({ key: 'editor.saved' }); },
      (err) => {
        setSaveStatus({ key: 'editor.saveFailed', error: err });
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
  // and the <Editor key={openNoteId}> remount App does when switching straight to a different note). A
  // failure here can't show a local banner — the editor is already gone by the time it lands — so it goes
  // to the App-level banner via onSaveError instead of being swallowed.
  React.useEffect(() => () => {
    flushRef.current().catch((error) => onSaveError({ key: 'editor.saveFailed', error }));
  }, []);

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
    setFindMsg(null);
    const ta = textareaRef.current;
    if (ta) {
      const sel = ta.value.slice(ta.selectionStart, ta.selectionEnd);
      if (sel) setNeedle(sel);
    }
  }, [findOpen]);

  const findNext = () => {
    const ta = textareaRef.current;
    if (!ta || !needle) { setFindMsg({ key: 'find.none' }); return false; }
    const text = ta.value;
    let idx = text.indexOf(needle, ta.selectionEnd);
    if (idx === -1) idx = text.indexOf(needle, 0);
    if (idx === -1) { setFindMsg({ key: 'find.none' }); return false; }
    ta.focus();
    ta.setSelectionRange(idx, idx + needle.length);
    setFindMsg({ key: 'find.count', vars: { n: countOccurrences(text, needle) } });
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
    if (count === 0) { setFindMsg({ key: 'find.none' }); return; }
    const newText = text.split(needle).join(replacement);
    applyReplacement(ta, 0, text.length, newText);
    setFindMsg({ key: 'find.replaced', vars: { n: count } });
  };

  const exportTxt = () => {
    const failed = (error) => setExportMsg({ error });
    window.SoriBridge.pickSavePath(`${title}.txt`, t('filter.txt')).then((path) => {
      if (!path) return;
      flushSave().then(
        () => {
          window.SoriBridge.exportNote(noteId, path).then(() => setExportMsg({ key: 'export.done' }), failed);
        },
        (error) => setExportMsg({ key: 'export.saveFailed', error }),
      );
    }, failed);
  };

  return (
    <div className="editor">
      <div className="editor-header">
        {/* ponytail: fires the flush PATCH without awaiting it before onClose()'s refresh() GET, so on a
            slow save the list can briefly show the pre-edit title for one refresh cycle. Upgrade path:
            await flushSave() before calling onClose() (needs onClose to be async-aware). */}
        <button className="btn" onClick={() => { flushSave().catch((error) => onSaveError({ key: 'editor.saveFailed', error })); onClose(); }}>{t('editor.back')}</button>
        <input
          className="editor-title"
          value={title}
          disabled={!loaded}
          onChange={(e) => setTitle(e.target.value)}
        />
        <span className="save-status"><Msg m={saveStatus} /></span>
        <button className="btn" disabled={jobRunningHere} onClick={exportTxt}>{t('editor.export')}</button>
      </div>
      {loadError && <div className="modal-error"><Msg m={loadError} /></div>}
      {exportMsg && <div className="editor-note"><Msg m={exportMsg} /></div>}
      {/* A live recording's status lives only in the LivePill. */}
      {jobRunningHere && job.op === 'transcribe' && (
        <div className="job-status">
          <span className="job-stage">{fileStatus(job)}</span>
          <CancelButton />
        </div>
      )}
      {findOpen && (
        <div className="find-panel">
          {jobRunningHere ? (
            <span className="modal-hint">{t('find.locked')}</span>
          ) : (
            <React.Fragment>
              <input
                className="find-input"
                placeholder={t('find.needle')}
                value={needle}
                onChange={(e) => setNeedle(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') findNext(); }}
              />
              <input
                className="find-input"
                placeholder={t('find.replacement')}
                value={replacement}
                onChange={(e) => setReplacement(e.target.value)}
              />
              <button className="btn" onClick={findNext}>{t('find.next')}</button>
              <button className="btn" onClick={replaceOne}>{t('find.replace')}</button>
              <button className="btn" onClick={replaceAll}>{t('find.replaceAll')}</button>
              {findMsg && <span className="find-msg"><Msg m={findMsg} /></span>}
            </React.Fragment>
          )}
        </div>
      )}
      <textarea
        ref={textareaRef}
        className="editor-textarea"
        value={jobRunningHere ? job.text : transcript}
        readOnly={jobRunningHere || !loaded || reloadingTranscript}
        onChange={(e) => setTranscript(e.target.value)}
      />
    </div>
  );
};

// The only live-recording status. Its words come from the job's phase / source / recorded_seconds; the timer is the
// server's recorded time, so it starts when recording does, not while the model loads. After the job ends the pill
// stays mounted with the last state and `hidden`, so the CSS exit transition can play.
const LivePill = ({ job }) => {
  const isLive = job.state === 'running' && job.op === 'listen';
  const lastRef = React.useRef(null);
  if (isLive) lastRef.current = job;
  // Answers the click before the next poll says 'finishing'. Cleared only when a new recording starts, so the
  // stop button can't reappear while the pill fades out.
  const [stopping, setStopping] = React.useState(false);
  React.useEffect(() => { if (isLive) setStopping(false); }, [isLive]);
  const shown = lastRef.current;
  if (!shown) return null;

  const phase = stopping ? 'finishing' : shown.phase;
  const preparing = !phase || phase === 'loading';
  const finishing = phase === 'finishing';
  const recording = !preparing && !finishing;
  const seconds = Math.floor(shown.recorded_seconds || 0);
  const onStop = () => {
    setStopping(true);
    window.SoriBridge.stopLive().catch(() => setStopping(false));
  };

  return (
    <div className="live-pill" hidden={!isLive}>
      <span className={`live-dot${recording ? '' : ' is-idle'}`} aria-hidden="true" />
      {recording && <span className="live-time">{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</span>}
      <span className="live-label" role="status">
        {preparing ? t('phase.loading') : finishing ? t('live.finishing')
          : t('live.recording', { source: t(`live.source.${shown.source || 'mic'}`) })}
      </span>
      {/* always laid out while recording, only faded in, so a segment starting never moves the stop button */}
      {recording && <span className={`live-busy${phase === 'transcribing' ? ' is-on' : ''}`}>{t('live.busy')}</span>}
      {!finishing && (
        <button className="live-stop" disabled={!isLive} onClick={onStop}>
          <span className="live-stop-glyph" aria-hidden="true" />{t('live.stop')}
        </button>
      )}
    </div>
  );
};

// File-transcription progress on the list screen (the editor shows its own), plus the drag & drop queue.
const JobPill = ({ job, queued }) => {
  if (!(job.state === 'running' && job.op === 'transcribe') && !queued) return null;
  return (
    <div className="live-pill job-pill">
      {job.state === 'running' && job.op === 'transcribe' ? (
        <React.Fragment>
          <span className="live-label">{fileStatus(job)}</span>
          <CancelButton key={job.note_id} />
        </React.Fragment>
      ) : <span className="live-label">{t('job.queued')}</span>}
      {queued > 0 && <span className="job-queue">{t('job.queueCount', { n: queued })}</span>}
    </div>
  );
};

// First run: the models aren't on disk yet. Shows the setup job's per-file progress from GET /job.
// First-run setup, in user terms: three groups (the backend's ("step", …) events) instead of file paths, one progress
// bar for whatever is downloading now, and the raw error only behind 자세히.
const SETUP_STEPS = ['speech', 'speaker', 'audio'];
const formatMib = (mib) => (mib >= 1024 ? `${(mib / 1024).toFixed(1)} GB` : `${Math.round(mib)} MB`);
const CheckGlyph = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false">
    <path d="M2.5 6.2l2.3 2.3 4.7-4.9" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const SetupScreen = ({ job, error, onRetry, lang, onLang }) => {
  const mine = job.op === 'setup';
  const running = mine && job.state === 'running';
  const failed = (mine && job.state === 'error') || Boolean(error);
  const current = mine ? SETUP_STEPS.indexOf(job.step) : -1;
  const downloading = running && job.file && !(job.ready || []).includes(job.file) && (job.progress || []).length === 3;
  const [, doneMib, totalMib] = downloading ? job.progress : [];
  const stateOf = (index) => {
    if (mine && job.state === 'done' && !error) return 'done';
    if (current < 0 || index > current) return 'pending';
    if (index < current) return 'done';
    return failed ? 'failed' : running ? 'active' : 'pending';
  };
  return (
    <div className="setup-screen">
      <div className="setup-drag" data-tauri-drag-region />
      <div className="setup-lang"><LangToggle lang={lang} onChange={onLang} /></div>
      <div className="setup-card">
        <img className="setup-icon" src="icon.png" alt="" />
        <h1 className="setup-title">{failed ? t('setup.titleFailed') : t('setup.title')}</h1>
        <p className="setup-lead">
          {t('setup.lead', { size: mine && job.size ? t('setup.size', { size: formatMib(job.size) }) : '' })}
        </p>
        <ol className="setup-steps" aria-live="polite">
          {SETUP_STEPS.map((key, index) => {
            const state = stateOf(index);
            const label = t(`setup.${key}`);
            return (
              <li key={key} className={`setup-step is-${state}`}>
                <span className="setup-mark" aria-hidden="true">{state === 'done' ? <CheckGlyph /> : state === 'failed' ? '!' : index + 1}</span>
                <div className="setup-step-body">
                  <div className="setup-step-label">
                    {label}
                    <span className="sr-only">{t(`setup.state.${state}`)}</span>
                  </div>
                  {state === 'active' ? (
                    <React.Fragment>
                      <div className={`setup-bar${downloading ? '' : ' is-busy'}`} role="progressbar" aria-label={label}
                        aria-valuemin={0} aria-valuemax={100} aria-valuenow={downloading ? job.percent : undefined}>
                        <div className="setup-bar-fill" style={downloading ? { width: `${job.percent}%` } : undefined} />
                      </div>
                      <div className="setup-step-hint">
                        {downloading ? `${formatMib(doneMib)} / ${formatMib(totalMib)}`
                          : t(job.phase === 'converting' ? 'setup.converting' : 'setup.checking')}
                      </div>
                    </React.Fragment>
                  ) : (
                    <div className="setup-step-hint">{t(`setup.${key}.hint`)}</div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
        {failed && (
          <div className="setup-error" role="alert">
            <p>{t('setup.errorHelp')}</p>
            <details>
              <summary>{t('details')}</summary>
              <pre>{[mine && job.error, error && (rawError(error.error) || say(error)[0])].filter(Boolean).join('\n')}</pre>
            </details>
          </div>
        )}
        {/* an ended setup job while this screen is still up means the models are still incomplete */}
        {running ? (
          <p className="setup-foot">{t('setup.foot')}</p>
        ) : (
          <button className="btn btn-primary setup-action" onClick={onRetry}>{mine || error ? t('setup.retry') : t('setup.start')}</button>
        )}
      </div>
    </div>
  );
};

// The window has no OS frame (tauri.conf.json decorations: false). Its caption buttons are ported from note-taking's
// window-caption-buttons.jsx: the same glyphs, 40 px columns the height of the top bar, a 26 px hover disc (yellow /
// green / red), blur after a click. Portalled to the top-right corner above every overlay, so no modal or screen can
// leave the window without a close button.
const currentWindow = () => {
  try { return window.__TAURI__.window.getCurrentWindow(); } catch (e) { return null; }
};
// Inline SVG, not Segoe Fluent Icons: that font is missing on some Windows installs and would render as tofu.
const MinimizeGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <path d="M0 5h10" stroke="currentColor" strokeWidth="1" fill="none" shapeRendering="crispEdges" />
  </svg>
);
const MaximizeGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <rect x="0.5" y="0.5" width="9" height="9" rx="1" stroke="currentColor" strokeWidth="1" fill="none" shapeRendering="crispEdges" />
  </svg>
);
const RestoreGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <path d="M2.5 2.5V1.5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-1" stroke="currentColor" strokeWidth="1" fill="none" />
    <rect x="0.5" y="2.5" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1" fill="none" shapeRendering="crispEdges" />
  </svg>
);
const CloseGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <path d="M0.5 0.5l9 9M9.5 0.5l-9 9" stroke="currentColor" strokeWidth="1.1" fill="none" />
  </svg>
);

const WindowCaption = () => {
  const [maximized, setMaximized] = React.useState(false);
  // The glyph follows the window, not a click counter: Aero Snap, a double-click on the drag region or the taskbar
  // can maximize it too.
  React.useEffect(() => {
    const win = currentWindow();
    if (!win) return undefined;
    let disposed = false;
    let unlisten = null;
    const sync = () => win.isMaximized().then((value) => { if (!disposed) setMaximized(value); }, () => {});
    sync();
    win.onResized(sync).then((remove) => { if (disposed) remove(); else unlisten = remove; }, () => {});
    return () => { disposed = true; if (unlisten) unlisten(); };
  }, []);
  const run = (method) => (event) => {
    event.currentTarget.blur(); // OS caption buttons never keep focus; keyboard users still get :focus-visible
    const win = currentWindow();
    if (win) win[method]().catch((error) => console.warn(`window ${method} failed`, error));
  };
  const button = (className, label, method, glyph) => (
    <button type="button" className={`caption-btn ${className}`} title={label} aria-label={label} onClick={run(method)}>
      <span className="caption-disc" aria-hidden="true">{glyph}</span>
    </button>
  );
  return ReactDOM.createPortal(
    <div className="caption">
      {button('caption-min', t('caption.min'), 'minimize', <MinimizeGlyph />)}
      {button('caption-max', maximized ? t('caption.restore') : t('caption.max'), 'toggleMaximize', maximized ? <RestoreGlyph /> : <MaximizeGlyph />)}
      {/* close(), never destroy(): CloseRequested finishes a live recording and keeps its WAV before the app exits. */}
      {button('caption-close', t('caption.close'), 'close', <CloseGlyph />)}
    </div>,
    document.body,
  );
};

const TopBar = ({ query, setQuery, folders, folderFilter, setFolderFilter, onNewNote, lang, onLang }) => {
  const [filterOpen, setFilterOpen] = React.useState(false);
  const activeFolder = folders.find((f) => f.id === folderFilter);
  return (
    <header className="topbar" data-tauri-drag-region>
      <div className="brand" data-tauri-drag-region>{t('brand')}</div>
      <input
        className="search"
        placeholder={t('search')}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="dropdown">
        <button className="btn" onClick={() => setFilterOpen((v) => !v)}>
          {activeFolder ? t('filter.active', { name: activeFolder.name }) : t('filter')}
        </button>
        {filterOpen && (
          <div className="dropdown-menu">
            <button className="dropdown-item" onClick={() => { setFolderFilter(null); setFilterOpen(false); }}>{t('filter.all')}</button>
            {folders.map((f) => (
              <button key={f.id} className="dropdown-item" onClick={() => { setFolderFilter(f.id); setFilterOpen(false); }}>{f.name}</button>
            ))}
          </div>
        )}
      </div>
      <button className="btn btn-primary" onClick={onNewNote}>{t('newNote')}</button>
      {/* Empty drag area, then room for the fixed caption buttons (Tauri drags only on direct clicks on these). */}
      <div className="drag-spacer" data-tauri-drag-region />
      <LangToggle lang={lang} onChange={onLang} />
      <div className="caption-reserve" aria-hidden="true" />
    </header>
  );
};

// Stroke icons for the sidebar (inline SVG, like the caption glyphs, so no icon font is needed).
const NAV_ICONS = {
  all: <path d="M4 6h16M4 12h16M4 18h10" />,
  starred: <path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" />,
  live: <React.Fragment><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" /></React.Fragment>,
  trash: <path d="M4 7h16M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13" />,
  folder: <path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4l2 2h8a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z" />,
};
const NavIcon = ({ name }) => (
  <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{NAV_ICONS[name]}</svg>
);

const Sidebar = ({ view, setView, liveCount, folders, onCreateFolder, onDeleteFolder, collapsed, setCollapsed }) => {
  const [addingFolder, setAddingFolder] = React.useState(false);
  const [folderName, setFolderName] = React.useState('');

  const submitFolder = () => {
    const name = folderName.trim();
    if (name) onCreateFolder(name);
    setAddingFolder(false);
    setFolderName('');
  };

  // Collapsed, the sidebar is an icon rail: the name moves to the tooltip / accessible name, and folders (which would
  // all show the same icon) stay in the expanded sidebar.
  return (
    <nav className="sidebar">
      {!collapsed && <div className="sidebar-label">{t('sidebar.mine')}</div>}
      {VIEWS.map((key) => (
        <button key={key} className={`nav-item${view === key ? ' active' : ''}`} onClick={() => setView(key)}
          title={collapsed ? t(`view.${key}`) : undefined} aria-label={collapsed ? t(`view.${key}`) : undefined}>
          <NavIcon name={key} />
          {!collapsed && <span className="nav-label">{t(`view.${key}`)}</span>}
          {key === 'live' && liveCount > 0 && <span className="badge">{liveCount}</span>}
        </button>
      ))}
      {!collapsed && (
        <div className="sidebar-row">
          <div className="sidebar-label">{t('sidebar.folders')}</div>
          <button className="icon-btn" aria-label={t('folder.add')} onClick={() => setAddingFolder(true)}>+</button>
        </div>
      )}
      {!collapsed && addingFolder && (
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
      {!collapsed && folders.map((f) => (
        <div key={f.id} className="folder-item">
          <button className={`nav-item${view === `folder:${f.id}` ? ' active' : ''}`} onClick={() => setView(`folder:${f.id}`)}>
            <NavIcon name="folder" />
            <span className="nav-label">{f.name}</span>
          </button>
          <button className="folder-delete" aria-label={t('folder.delete')} onClick={() => onDeleteFolder(f.id)}>×</button>
        </div>
      ))}
      <button className="collapse-btn" aria-label={t(collapsed ? 'sidebar.expand' : 'sidebar.collapse')}
        title={t(collapsed ? 'sidebar.expand' : 'sidebar.collapse')} onClick={() => setCollapsed((v) => !v)}>
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
        <input type="checkbox" checked={selected} onChange={() => onToggleSelect(note.id)} aria-label={t('row.select', { title: note.title })} />
      </td>
      <td className="col-title">
        <div className="title-line">
          {note.starred ? <span className="star" aria-hidden="true">★</span> : null}
          <span className="title">{note.title}</span>
          {interrupted && <span className="chip chip-danger">{t('row.interrupted')}</span>}
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
  const emptyText = view === 'trash' ? t('table.trashEmpty') : t('table.empty');

  return (
    <table className="table">
      <thead>
        <tr>
          <th className="col-check">
            <input type="checkbox" checked={allSelected} onChange={() => onToggleSelectAll(allIds)} aria-label={t('table.selectAll')} />
          </th>
          {COLUMNS.map((key) => (
            <th key={key}>
              <button className="sort-btn" onClick={() => onSort(key)}>
                {t(`col.${key}`)} {sort.key === key ? (sort.dir === 'asc' ? '▲' : '▼') : ''}
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
    <span>{t('action.count', { n: count })}</span>
    {view === 'trash' ? (
      <React.Fragment>
        <button className="btn" onClick={onRestore}>{t('action.restore')}</button>
        <button className="btn btn-danger" onClick={onDeleteForever}>{t('action.deleteForever')}</button>
      </React.Fragment>
    ) : (
      <React.Fragment>
        <button className="btn" onClick={onToggleStar}>{t('action.star')}</button>
        <select
          className="folder-select"
          aria-label={t('action.move')}
          defaultValue=""
          onChange={(e) => {
            const value = e.target.value;
            if (value === '') return;
            onMoveFolder(value === 'none' ? null : Number(value));
            e.target.value = '';
          }}
        >
          <option value="" disabled>{t('action.move')}</option>
          <option value="none">{t('action.noFolder')}</option>
          {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <button className="btn" onClick={onTrash}>{t('action.trash')}</button>
      </React.Fragment>
    )}
    <button className="btn" onClick={onClear}>{t('action.clear')}</button>
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
  const [devices, setDevices] = React.useState(null); // null = GET /devices hasn't answered yet
  const [setupNeeded, setSetupNeeded] = React.useState(false);
  const [dragging, setDragging] = React.useState(false);
  const [queue, setQueue] = React.useState([]); // dropped audio paths not yet started
  // Read by the once-registered Tauri event listeners below, which would otherwise see the first render's values.
  const jobRef = React.useRef(job);
  jobRef.current = job;
  const devicesRef = React.useRef(devices);
  devicesRef.current = devices;
  const setupNeededRef = React.useRef(setupNeeded);
  setupNeededRef.current = setupNeeded;
  const [chooserOpen, setChooserOpen] = React.useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false);
  const [lang, setLang] = React.useState(uiLang);
  const changeLang = (value) => {
    uiLang = value;
    document.documentElement.lang = value;
    try { localStorage.setItem('sori.lang', value); } catch (e) { /* private mode: not remembered */ }
    setLang(value);
  };
  const [error, setError] = React.useState(null); // a message descriptor for <Msg>, see say()
  // Whether the CURRENT `error` was set by refresh() itself, vs. by someone else (job-error poll, runBulk,
  // folder actions, save-on-close). refresh() runs constantly (search typing, closing the editor, ...) and
  // must never wipe out an error it didn't cause — so its own success path only clears the banner when it
  // owns it. showError()/the banner's "×" mark ownership as "not refresh" / "none" respectively.
  const errorFromRefresh = React.useRef(false);
  const showError = (msg) => { errorFromRefresh.current = false; setError(msg); };
  const showFailure = (err) => showError({ error: err });
  const dismissError = () => { errorFromRefresh.current = false; setError(null); };

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
    return Promise.all([window.SoriBridge.notes(v, q), window.SoriBridge.folders(), window.SoriBridge.notes('live')]).then(
      ([n, f, live]) => {
        if (seq !== requestSeq.current) return;
        setNotes(n); setFolders(f); setLiveCount(live.length);
        if (errorFromRefresh.current) { errorFromRefresh.current = false; setError(null); }
      },
      (err) => {
        if (seq !== requestSeq.current) return;
        errorFromRefresh.current = true;
        setError({ error: err });
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
          if (!pollingRef.current) return; // the loop was stopped (unmount cleanup below) while this request was in flight
          const first = awaitingFirst;
          awaitingFirst = false;
          setJob((prev) => {
            if (j.state !== 'running' && (first || prev.state === 'running')) {
              if (j.op === 'setup') loadDevices(); // models_ready decides whether the setup screen goes away
              refresh();
              // No need to chain after refresh() any more: refresh()'s success path only clears an error
              // it set itself (see errorFromRefresh above), so this message survives regardless of order.
              // A failed setup is shown on the setup screen itself (with 다시 시도), not in the banner.
              // A user-initiated 취소 is not an error worth a banner: the pill/editor simply stop.
              if (j.state === 'error' && j.op !== 'setup' && j.code !== 'cancelled') {
                showError(j.error ? { error: { message: j.error, code: j.code } } : { key: 'err.jobFailed' });
              }
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

  // Called from the poll loop above and from once-registered effects/listeners; only touches setters, refs
  // and startPolling (whose state lives in refs), so a stale closure of these is harmless.
  const loadDevices = () => window.SoriBridge.devices().then(
    (d) => { setDevices(d.devices); setSetupNeeded(!d.models_ready); return d; },
    (err) => { showFailure(err); return null; },
  );
  // 409 = a job is already running (e.g. the setup this app started before a relaunch): just follow it.
  const startSetup = () => window.SoriBridge.setup().then(
    () => startPolling(),
    (err) => { if (err.status === 409) startPolling(); else showFailure(err); },
  );
  React.useEffect(() => {
    loadDevices().then((d) => { if (d && !d.models_ready) startSetup(); });
  }, []);
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

  React.useEffect(() => {
    window.SoriBridge.onDrag((type, payload) => {
      setDragging(type === 'enter' || type === 'over');
      if (type !== 'drop' || setupNeededRef.current) return; // no models yet: nothing to transcribe with
      const paths = payload.paths || [];
      const audio = paths.filter(window.SoriBridge.isAudio);
      if (audio.length) setQueue((q) => [...q, ...audio]);
      if (audio.length < paths.length) showError({ key: 'err.audioOnly' });
    });
  }, []);
  // Dropped files run one after another (one model job at a time). The job is marked running optimistically so
  // this effect never double-starts before the first poll lands; a 409 (another job) just waits for it to end.
  // Keyed on the whole `job` object (a new one per poll), not just job.state: if the blocking job ends before
  // the 409's poll lands and state goes e.g. 'done' -> 'done', the queue would otherwise never retry.
  // startPolling's first tick always counts as a transition, so an instantly-finished queued job still refreshes.
  const startingRef = React.useRef(false);
  React.useEffect(() => {
    if (!queue.length || !devices || setupNeeded || job.state === 'running' || startingRef.current) return;
    startingRef.current = true;
    const path = queue[0];
    window.SoriBridge.transcribe(path, pickDevice(devices, loadLive().device), loadLive().speakers !== false).then(
      ({ note_id }) => {
        startingRef.current = false;
        setQueue((q) => q.slice(1));
        setJob((prev) => ({ ...prev, state: 'running', op: 'transcribe', note_id, stage: '준비 중', phase: 'loading', percent: 0, text: '' }));
        startPolling();
        refresh();
      },
      (err) => {
        startingRef.current = false;
        if (err.status === 409) { startPolling(); return; }
        setQueue((q) => q.slice(1));
        showError({ key: 'err.file', vars: { name: path.split(/[\\/]/).pop() }, error: err });
      },
    );
  }, [queue, job, devices, setupNeeded]);

  // The tray's 녹음 시작 item reads ⏹ 녹음 마치기 while a live recording runs; tray and window title follow the language.
  const recording = job.state === 'running' && job.op === 'listen';
  React.useEffect(() => { window.SoriBridge.setRecording(recording, lang); }, [recording, lang]);

  // Ctrl+Shift+R and the tray's 녹음 시작: stop a live recording, or start one with the last chooser choice.
  // Stopping from here shows 'finishing' in the LivePill too: /live/stop sets the job's phase right away.
  React.useEffect(() => {
    window.SoriBridge.onToggleRecording(() => {
      if (setupNeededRef.current) return;
      const current = jobRef.current;
      if (current.state === 'running') {
        if (current.op === 'listen') window.SoriBridge.stopLive().catch(showFailure);
        else showError({ key: 'err.busy' });
        return;
      }
      const list = devicesRef.current;
      if (!list || !list.length) return;
      const saved = loadLive();
      const source = saved.source || 'mic';
      const begin = (mic) => window.SoriBridge.startLive(mic, pickDevice(list, saved.device), source).then(
        ({ note_id }) => { setChooserOpen(false); startPolling(); openNote(note_id); refresh(); },
        showFailure,
      );
      if (source === 'system') { begin(''); return; }
      window.SoriBridge.mics().then((mics) => {
        const mic = mics.includes(saved.mic) ? saved.mic : mics[0];
        if (mic) begin(mic); else showError({ key: 'err.noMicFound' });
      }, showFailure);
    });
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
      if (failed) showFailure(failed.reason);
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
    if (!window.confirm(t('confirm.deleteNotes'))) return;
    runBulk((id) => window.SoriBridge.deleteNote(id));
  };

  const createFolder = (name) => window.SoriBridge.createFolder(name).then(refresh, showFailure);
  const deleteFolderById = (id) => {
    if (!window.confirm(t('confirm.deleteFolder'))) return;
    window.SoriBridge.deleteFolder(id).then(
      () => {
        if (view === `folder:${id}`) setView('all');
        if (folderFilter === id) setFolderFilter(null); // the deleted folder can no longer filter the table
        refresh();
      },
      showFailure,
    );
  };

  const findFolderName = (id) => {
    const f = folders.find((x) => x.id === id);
    return f ? f.name : '';
  };
  const heading = view.startsWith('folder:')
    ? findFolderName(Number(view.slice('folder:'.length)))
    : (VIEWS.includes(view) ? t(`view.${view}`) : '');

  // After every hook above (rules of hooks): the first-run download replaces the whole dashboard.
  if (setupNeeded) {
    return (
      <React.Fragment>
        <SetupScreen job={job} error={error} lang={lang} onLang={changeLang} onRetry={() => { dismissError(); startSetup(); }} />
        <WindowCaption />
      </React.Fragment>
    );
  }

  return (
    <div className={`app${sidebarCollapsed ? ' collapsed' : ''}`}>
      <TopBar
        query={query}
        setQuery={setQuery}
        folders={folders}
        folderFilter={folderFilter}
        setFolderFilter={setFolderFilter}
        onNewNote={() => setChooserOpen(true)}
        lang={lang}
        onLang={changeLang}
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
        {error && (
          <div className="banner">
            <span><Msg m={error} /></span>
            <button className="banner-close" aria-label={t('caption.close')} onClick={dismissError}>×</button>
          </div>
        )}
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
            onSaveError={showError}
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
      <Chooser open={chooserOpen} job={job} devices={devices} onClose={() => setChooserOpen(false)} startPolling={startPolling} openNote={openNote} />
      <LivePill job={job} />
      {!openNoteId && <JobPill job={job} queued={queue.length} />}
      {dragging && (
        <div className="drop-overlay" aria-hidden="true">
          <div className="drop-hint">{t('drop.hint')}</div>
        </div>
      )}
      <WindowCaption />
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
