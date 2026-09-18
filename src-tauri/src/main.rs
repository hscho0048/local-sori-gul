#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, RunEvent, WindowEvent};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

struct Bridge {
    child: Mutex<Option<Child>>,
    url: String,
    token: String,
}

#[tauri::command]
fn bridge(state: tauri::State<Bridge>) -> (String, String) {
    (state.url.clone(), state.token.clone())
}

/// Tray items: open, record, quit.
struct TrayItems([MenuItem<tauri::Wry>; 3]);

/// Tray and title follow the app: the frontend reports whenever a live recording starts or ends or the language changes.
#[tauri::command]
fn set_recording(recording: bool, lang: String, app: AppHandle, items: tauri::State<TrayItems>) {
    let (texts, title) = tray_texts(&lang, recording);
    for (item, text) in items.0.iter().zip(texts) {
        let _ = item.set_text(text);
    }
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_title(title);
    }
    if let Some(tray) = app.tray_by_id("main") {
        let _ = tray.set_tooltip(Some(title));
    }
}

/// (open, record, quit) labels and the window title; anything but "en" is Korean.
fn tray_texts(lang: &str, recording: bool) -> ([&'static str; 3], &'static str) {
    match (lang == "en", recording) {
        (false, false) => (["열기", "녹음 시작", "종료"], "소리글"),
        (false, true) => (["열기", "⏹ 녹음 마치기", "종료"], "소리글"),
        (true, false) => (["Open", "Start recording", "Quit"], "Sorigul"),
        (true, true) => (["Open", "⏹ Stop recording", "Quit"], "Sorigul"),
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn tray_follows_language_and_recording() {
        assert_eq!(super::tray_texts("ko", false), (["열기", "녹음 시작", "종료"], "소리글"));
        assert_eq!(super::tray_texts("ko", true).0[1], "⏹ 녹음 마치기");
        assert_eq!(super::tray_texts("en", false), (["Open", "Start recording", "Quit"], "Sorigul"));
        assert_eq!(super::tray_texts("en", true).0[1], "⏹ Stop recording");
    }
}

/// One app per data folder. A second launch (a double double-click) used to come up without a window but with its
/// own tray icon, bridge and hotkey. The OS drops the lock when the process ends, crash included.
fn lock_instance(home: &std::path::Path) -> Option<std::fs::File> {
    use std::os::windows::fs::OpenOptionsExt;
    std::fs::OpenOptions::new().write(true).create(true).share_mode(0).open(home.join("app.lock")).ok()
}

#[link(name = "user32")]
extern "system" {
    fn FindWindowW(class: *const u16, title: *const u16) -> isize;
    fn IsIconic(window: isize) -> i32;
    fn ShowWindow(window: isize, command: i32) -> i32;
    fn SetForegroundWindow(window: isize) -> i32;
}

/// Brings the already running instance's window to the front.
// ponytail: found by its title "소리글" or "Sorigul" (it follows the language); another top-level window with exactly
// that title would be picked instead — switch to a named pipe / tauri-plugin-single-instance if that ever happens.
fn focus_running_instance() {
    for name in ["소리글", "Sorigul"] {
        let title: Vec<u16> = name.encode_utf16().chain(Some(0)).collect();
        let window = unsafe { FindWindowW(std::ptr::null(), title.as_ptr()) };
        if window != 0 {
            // SW_RESTORE only when minimized: on a maximized window it would un-maximize it.
            unsafe {
                ShowWindow(window, if IsIconic(window) != 0 { 9 } else { 5 }); // SW_RESTORE : SW_SHOW
                SetForegroundWindow(window);
            }
            return;
        }
    }
}

/// (pythonw.exe, working dir with server.py, SORIGUL_HOME). Debug: the repo's .venv, backend/ and data, so dev data
/// keeps working. Release: the embeddable Python bundled as the `python` resource (resource dir = the exe's dir on
/// Windows) and %LOCALAPPDATA%\Sorigul for models, library and the model lock.
fn bridge_paths() -> (PathBuf, PathBuf, PathBuf) {
    if cfg!(debug_assertions) {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf();
        (root.join(".venv").join("Scripts").join("pythonw.exe"), root.join("backend"), root)
    } else {
        let python = std::env::current_exe().expect("no exe path").parent().unwrap().join("python");
        let home = PathBuf::from(std::env::var_os("LOCALAPPDATA").expect("LOCALAPPDATA is not set")).join("Sorigul");
        (python.join("pythonw.exe"), python, home)
    }
}

fn spawn_bridge(python: PathBuf, cwd: PathBuf, home: PathBuf) -> Bridge {
    let mut child = Command::new(&python)
        .arg("server.py")
        .current_dir(&cwd)
        .env("SORIGUL_HOME", &home)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap_or_else(|e| panic!("cannot start {}: {e} (dev: run setup.cmd first)", python.display()));
    let mut line = String::new();
    BufReader::new(child.stdout.take().unwrap()).read_line(&mut line).expect("bridge did not start");
    let parts: Vec<&str> = line.split_whitespace().collect();
    if parts.len() != 3 || parts[0] != "PORT" {
        let _ = child.kill();
        panic!("bridge printed {line:?} instead of 'PORT <n> <token>'");
    }
    Bridge { url: format!("http://127.0.0.1:{}", parts[1]), token: parts[2].to_string(), child: Mutex::new(Some(child)) }
}

/// Closing stdin lets server.py finish a live recording (text + WAV) or cancel another job, releasing
/// .model.lock; kill it only if that takes longer than server.py's own 30 s wait.
fn stop_bridge(state: &Bridge) {
    let Some(mut child) = state.child.lock().unwrap().take() else { return };
    drop(child.stdin.take());
    let deadline = Instant::now() + Duration::from_secs(35);
    while Instant::now() < deadline {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
    let _ = child.wait();
}

fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn main() {
    let (python, cwd, home) = bridge_paths();
    std::fs::create_dir_all(&home).expect("cannot create the data folder");
    let Some(_instance) = lock_instance(&home) else {
        focus_running_instance();
        return;
    };
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        let _ = app.emit("toggle-recording", ());
                    }
                })
                .build(),
        )
        .manage(spawn_bridge(python, cwd, home))
        .invoke_handler(tauri::generate_handler![bridge, set_recording])
        .setup(|app| {
            // ponytail: if another program owns Ctrl+Shift+R the shortcut is just unavailable (tray still works);
            // add a user-chosen binding if conflicts get reported.
            if let Err(error) = app.global_shortcut().register("ctrl+shift+r") {
                eprintln!("Ctrl+Shift+R unavailable: {error}");
            }
            let open = MenuItem::with_id(app, "open", "열기", true, None::<&str>)?;
            let record = MenuItem::with_id(app, "record", "녹음 시작", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
            app.manage(TrayItems([open.clone(), record.clone(), quit.clone()]));
            TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("소리글")
                .menu(&Menu::with_items(app, &[&open, &record, &quit])?)
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "open" => show_main(app),
                    "record" => {
                        let _ = app.emit("toggle-recording", ());
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                // ponytail: the hidden window blocks the event loop while a recording finishes (<= 35 s);
                // move stop_bridge to a thread + exit event if the app ever needs to stay responsive then.
                let _ = window.hide();
                stop_bridge(&window.state::<Bridge>());
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build tauri app");
    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            stop_bridge(&handle.state::<Bridge>());
        }
    });
}
