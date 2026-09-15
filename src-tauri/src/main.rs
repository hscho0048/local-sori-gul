#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WindowEvent};

struct Bridge {
    child: Mutex<Option<Child>>,
    url: String,
    token: String,
}

#[tauri::command]
fn bridge(state: tauri::State<Bridge>) -> (String, String) {
    (state.url.clone(), state.token.clone())
}

fn spawn_bridge() -> Bridge {
    // ponytail: dev layout only (venv + server.py next to src-tauri); bundle python and the backend for a release build.
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf();
    let mut child = Command::new(root.join(".venv").join("Scripts").join("pythonw.exe"))
        .arg("server.py")
        .current_dir(&root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect(".venv is missing: run setup.cmd first");
    let mut line = String::new();
    BufReader::new(child.stdout.take().unwrap()).read_line(&mut line).expect("bridge did not start");
    let parts: Vec<&str> = line.split_whitespace().collect();
    if parts.len() != 3 || parts[0] != "PORT" {
        let _ = child.kill();
        panic!("bridge printed {line:?} instead of 'PORT <n> <token>'");
    }
    Bridge { url: format!("http://127.0.0.1:{}", parts[1]), token: parts[2].to_string(), child: Mutex::new(Some(child)) }
}

/// Closing stdin lets server.py cancel a running job (releasing .model.lock); kill it if that takes too long.
fn stop_bridge(state: &Bridge) {
    let Some(mut child) = state.child.lock().unwrap().take() else { return };
    drop(child.stdin.take());
    let deadline = Instant::now() + Duration::from_secs(3);
    while Instant::now() < deadline {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
    let _ = child.wait();
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(spawn_bridge())
        .invoke_handler(tauri::generate_handler![bridge])
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
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
