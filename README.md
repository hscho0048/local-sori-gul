# 소리글 (Sorigul)

인터넷 없이 내 PC에서 한국어 음성을 받아쓰는 Windows 데스크톱 앱입니다.
Whisper large-v3-turbo를 Snapdragon NPU·GPU, 인텔 GPU·NPU 또는 CPU에서 실행하고, 오디오와 받아쓰기는 PC 밖으로 나가지 않습니다.

> An offline Korean speech-to-text app for Windows (Snapdragon NPU/GPU, Intel GPU/NPU or CPU). The UI is available in Korean and English.

## 주요 기능

- **오디오 전사**: 오디오 파일(wav, mp3, m4a, flac, aac, ogg, opus, wma, mp4)을 받아씁니다. **화자 분리**를 켜면 문단마다 `화자 1:`, `화자 2:`가 붙습니다.
- **실시간 전사**: 말이 끊길 때마다 바로 받아써서 본문에 이어 붙이고, 녹음 파일(WAV)도 함께 보관합니다.
  - 소리 입력: **마이크**, **시스템 소리 (Zoom·Teams)**, **마이크 + 시스템 소리**
- **끌어 놓기**: 창에 오디오 파일을 끌어 놓으면 차례대로 전사합니다.
- **전사 취소**: 진행 중인 파일 전사를 취소해도 그때까지 받아쓴 내용은 남습니다.
- **보드 관리**: 폴더, 중요 표시, 휴지통, 검색, 찾아 바꾸기(Ctrl+H), TXT로 저장
- **단축키와 트레이**: 어느 창에서든 **Ctrl+Shift+R**로 녹음을 시작하고 마칩니다. 트레이 아이콘 메뉴는 열기 / 녹음 시작(녹음 중에는 ⏹ 녹음 마치기) / 종료입니다.
- **한국어 / English**: 위쪽 막대(첫 실행 화면에서는 오른쪽 위)의 **한 / EN**으로 화면과 트레이 메뉴의 언어를 바로 바꿉니다. 처음에는 Windows 표시 언어를 따릅니다.

## 연산 장치

앱은 PC에서 실제로 쓸 수 있는 장치만 목록에 보여 줍니다.

| 설치 파일 | 장치 | 비고 |
|---|---|---|
| ARM64 (Snapdragon X) | NPU (Hexagon), GPU (Adreno), CPU | NPU가 가장 빠르고, 화자 분리도 NPU에서 실행됩니다. |
| x64 (인텔·AMD) | 인텔 GPU (OpenVINO), 인텔 NPU (OpenVINO), CPU | 인텔 장치는 OpenVINO가 찾았을 때만 표시되고, 화자 분리는 CPU에서 실행됩니다. |

## 설치

1. [Releases](../../releases)에서 PC에 맞는 설치 파일을 내려받습니다.
   - Snapdragon 노트북: `Sorigul_<버전>_arm64-setup.exe`
   - 그 밖의 Windows PC: `Sorigul_<버전>_x64-setup.exe`
2. 설치 파일을 실행합니다. 코드 서명이 없어서 SmartScreen이 경고하면 **추가 정보 → 실행**을 누르세요.
3. 첫 실행 때 모델과 오디오 디코더(ffmpeg)를 한 번 내려받습니다. 내려받는 양은 ARM64가 약 3.4 GB, x64가 약 1.6 GB이고, 변환 파일까지 합치면 디스크를 ARM64에서 약 4.6 GB, x64에서 약 2.8 GB 씁니다. 받는 중에 앱을 닫아도 다음 실행 때 이어서 받습니다. 그 뒤로 전사에는 인터넷이 필요 없습니다.

요구 사항: Windows 10/11 64비트, 메모리 16 GB 이상 권장, 디스크 여유 공간 약 6 GB

## 데이터와 개인정보

- 모델, 받아쓰기 보관함(`library/`), 녹음 파일은 `%LOCALAPPDATA%\Sorigul`에 저장됩니다.
- 네트워크는 첫 실행 때 공개 모델과 ffmpeg를 내려받을 때만 씁니다. 출처는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 있습니다.
- 오디오와 텍스트는 어디로도 전송하지 않습니다.
- 앱을 제거해도 `%LOCALAPPDATA%\Sorigul`의 받아쓰기와 모델은 남습니다. 필요 없으면 직접 지우세요.

## 개발

### 준비 (한 번)

- Windows ARM64 또는 x64
- [Python 3.12](https://www.python.org/downloads/windows/): PC와 같은 아키텍처(ARM64 PC에는 ARM64 버전)
- [Node.js](https://nodejs.org/) LTS
- [Rust](https://rustup.rs/)
- Visual Studio Build Tools: C++ 데스크톱 개발 워크로드. ARM64 PC에서 x64 설치 파일도 만들려면 x64 빌드 도구까지 설치합니다.

```powershell
.\setup.cmd    # ARM64: .venv(QNN) + .venv-whisper-gpu / x64: .venv(OpenVINO), models\ 와 tools\ffmpeg.exe 내려받기
npm install
```

### 실행

```powershell
npm run tauri:dev    # dist\ 빌드 → src-tauri 디버그 빌드 → .venv의 server.py 실행 (데이터는 저장소 폴더 사용)
```

### 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_engine tests.test_diarize tests.test_library tests.test_server
```

### 설치 파일 만들기 (ARM64 PC에서 두 가지 모두)

```powershell
npm run tauri:build:arm64   # scripts\build-python-bundle.ps1 arm64 후 aarch64 NSIS 설치 파일
npm run tauri:build:x64     # scripts\build-python-bundle.ps1 x64 후 x86_64 NSIS 설치 파일 (크로스 빌드)
```

결과물은 `src-tauri\target\<triple>\release\bundle\nsis\Sorigul_<버전>_<arch>-setup.exe`에 생깁니다.
설치 파일에는 python.org 임베디드 Python, 아키텍처별 휠, 백엔드 `.py`, VC++ 런타임이 `python\` 폴더로 들어갑니다.

의존성이 바뀌면 두 번들을 만든 뒤 고지 파일을 다시 생성하세요.

```powershell
.\.venv\Scripts\python.exe scripts\third-party-notices.py
```

### 구조

| 파일 | 역할 |
|---|---|
| `src-tauri/src/main.rs` | 창·트레이·단축키, Python 브리지 프로세스 관리 |
| `app.jsx`, `bridge.js`, `tokens.css`, `index.html` | 화면 (React UMD, 번들러 없음) |
| `server.py` | 표준 라이브러리 HTTP 브리지 (토큰 인증, 127.0.0.1 전용) |
| `jobs.py` | 작업마다 모델 프로세스 하나 실행 |
| `engine.py` | Whisper 추론 (QNN NPU/GPU, OpenVINO, CPU), 실시간 전사 |
| `diarize.py` | 화자 분리 |
| `loopback.py` | WASAPI 시스템 소리 캡처 (ctypes) |
| `library.py` | SQLite 받아쓰기 보관함 |
| `setup_assets.py` | 첫 실행 모델·ffmpeg 내려받기 |
| `setup.cmd`, `setup.ps1`, `requirements-*.txt` | 개발 환경(가상환경·모델) 준비 |
| `scripts/` | 화면 빌드, 설치 파일용 Python 번들, 서드파티 고지 생성 |
| `tests/` | 백엔드 단위 테스트 |

## 라이선스

소리글은 [MIT 라이선스](LICENSE)로 배포합니다.
설치 파일에 포함되거나 첫 실행 때 내려받는 서드파티 구성 요소의 라이선스는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 있습니다.
에이투지체(A2Z) 글꼴(화면에 쓰는 Regular·Medium·SemiBold·Bold 네 굵기만 포함)은 [SIL Open Font License 1.1](A2Z/OFL.txt)을 따릅니다.
첫 실행 때 받는 ffmpeg는 GPL-3.0 빌드이며, 설치 파일에는 포함되지 않습니다.
