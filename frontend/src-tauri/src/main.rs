#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::Command;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use serde_json::json;
use tauri_plugin_store::StoreExt;

const STORE_PATH: &str = "config.json";
const DEFAULT_HOST: &str = "0.0.0.0";
const DEFAULT_PORT: &str = "8000";

/// App-managed state shared across commands.
struct AppState {
    lan_ip: Mutex<String>,
}

fn find_python() -> Option<PathBuf> {
    // First check PYTHON environment variable
    if let Ok(python_path) = env::var("PYTHON") {
        let p = PathBuf::from(&python_path);
        if p.exists() && Command::new(&p).arg("--version").output().is_ok() {
            return Some(p);
        }
    }

    // Try to find Python using where command on Windows (most reliable)
    if cfg!(target_os = "windows") {
        if let Ok(output) = Command::new("where").arg("python").output() {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout);
                if let Some(first_line) = path.lines().next() {
                    let p = PathBuf::from(first_line.trim());
                    if p.exists() {
                        return Some(p);
                    }
                }
            }
        }
    }

    // macOS: try python3
    if cfg!(target_os = "macos") {
        if Command::new("python3").arg("--version").output().is_ok() {
            return Some(PathBuf::from("python3"));
        }
    }

    // Then check common installation paths on Windows
    let possible_paths = [
        r"C:\Python314\python.exe",
        r"C:\Python313\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
        r"C:\Program Files\Python314\python.exe",
        r"C:\Program Files\Python313\python.exe",
        r"C:\Program Files\Python312\python.exe",
        r"C:\Program Files\Python311\python.exe",
        "python",
        "python3",
        "py",
    ];

    for path in possible_paths {
        if Command::new(path).arg("--version").output().is_ok() {
            return Some(PathBuf::from(path));
        }
    }

    None
}

/// Detect the local LAN IP address using the local-ip-address crate.
fn detect_lan_ip() -> String {
    local_ip_address::local_ip()
        .map(|ip| ip.to_string())
        .unwrap_or_else(|_| "127.0.0.1".to_string())
}

fn main() {
    let current_exe = std::env::current_exe().unwrap_or_default();
    let exe_dir = current_exe.parent().unwrap_or(&current_exe);

    // Get the resources directory for bundled apps
    let resources_dir = exe_dir.join("resources");

    // Search in multiple locations
    let possible_backend_paths = [
        // Same directory as exe (development build)
        exe_dir.to_path_buf(),
        // Backend in same folder as exe (direct build output)
        exe_dir.join("backend"),
        // Resources folder (for bundled apps) - Tauri puts resources here
        resources_dir.join("backend"),
        resources_dir.to_path_buf(),
        // Direct in resources
        exe_dir.join("resources").join("backend"),
        exe_dir.join("resources"),
        // NSIS installer structure - one level up from exe in release
        exe_dir.join("..").join("resources").join("backend"),
        exe_dir.join("..").join("resources"),
        exe_dir.join("..").to_path_buf(),
        // Bundle folder
        exe_dir.join("bundle").join("backend"),
        exe_dir.join("bundle"),
    ];

    let mut backend_exe = None;
    let mut backend_path = None;
    let mut python_backend = None;

    println!("Searching for backend...");
    println!("Exe dir: {:?}", exe_dir);
    println!("Resources dir: {:?}", resources_dir);

    // First, look for the PyInstaller executable
    for path in &possible_backend_paths {
        println!("Checking path: {:?}", path);

        let exe = path.join("ga-erp-backend.exe");
        if exe.exists() {
            backend_exe = Some(exe.clone());
            backend_path = Some(path.clone());
            println!("Found backend exe at: {:?}", exe);
            break;
        }

        // Also check in subdirectory "backend"
        let exe_in_backend = path.join("backend").join("ga-erp-backend.exe");
        if exe_in_backend.exists() {
            backend_exe = Some(exe_in_backend.clone());
            backend_path = Some(path.join("backend"));
            println!("Found backend exe at: {:?}", exe_in_backend);
            break;
        }

        // Check in dist subfolder (PyInstaller output)
        let exe_in_dist = path.join("dist").join("ga-erp-backend.exe");
        if exe_in_dist.exists() {
            backend_exe = Some(exe_in_dist.clone());
            backend_path = Some(path.join("dist"));
            println!("Found backend exe at: {:?}", exe_in_dist);
            break;
        }

        // Check for Python main.py in backend folder (IN resources/backend/)
        let py_main = path.join("main.py");
        if py_main.exists() {
            python_backend = Some(path.clone());
            println!("Found Python backend at: {:?}", py_main);
            break;
        }

        let py_in_backend = path.join("backend").join("main.py");
        if py_in_backend.exists() {
            python_backend = Some(path.join("backend"));
            println!("Found Python backend at: {:?}", py_in_backend);
            break;
        }
    }

    // Create shared handle to track the backend process for cleanup on exit
    let backend_child: Arc<Mutex<Option<std::process::Child>>> = Arc::new(Mutex::new(None));
    let backend_child_setup = backend_child.clone();
    let backend_child_cleanup = backend_child.clone();

    // Detect LAN IP early for managed state
    let detected_lan_ip = detect_lan_ip();

    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState {
            lan_ip: Mutex::new(detected_lan_ip.clone()),
        })
        .setup(move |app| {
            // Open or create the store
            let store = app.store(STORE_PATH)?;

            // Read mode from store (defaults to "server")
            let mode = store
                .get("lan_mode")
                .and_then(|v| v.as_str().map(String::from))
                .unwrap_or_else(|| "server".to_string());

            println!("App mode: {}", mode);
            println!("LAN IP: {}", detected_lan_ip);

            if mode == "client" {
                println!("CLIENT mode — skipping backend spawn");
                return Ok(());
            }

            // ── SERVER MODE ──────────────────────────────────────────
            println!("SERVER mode — spawning backend on {}:{}", DEFAULT_HOST, DEFAULT_PORT);

            // Start backend (prefer exe, fallback to Python)
            if let Some(bp) = backend_path {
                // Try to use the PyInstaller executable first
                if let Some(be) = backend_exe {
                    println!("Starting backend from executable: {:?}", be);

                    #[cfg(target_os = "windows")]
                    {
                        use std::os::windows::process::CommandExt;
                        const CREATE_NO_WINDOW: u32 = 0x08000000;

                        if let Ok(child) = Command::new(&be)
                            .creation_flags(CREATE_NO_WINDOW)
                            .current_dir(&bp)
                            .spawn()
                        {
                            *backend_child_setup.lock().unwrap() = Some(child);
                        }
                    }

                    #[cfg(not(target_os = "windows"))]
                    {
                        if let Ok(child) = Command::new(&be).current_dir(&bp).spawn() {
                            *backend_child_setup.lock().unwrap() = Some(child);
                        }
                    }

                    println!("Backend executable started");
                    thread::sleep(Duration::from_secs(4));
                }
            } else if let Some(bp) = python_backend {
                // Fallback: use Python
                if let Some(python) = find_python() {
                    println!("Using Python: {:?}", python);

                    // Check if dependencies work
                    let check = Command::new(&python)
                        .arg("-c")
                        .arg("import fastapi, sqlalchemy, uvicorn")
                        .current_dir(&bp)
                        .output();

                    if check.is_err() || !check.as_ref().unwrap().status.success() {
                        // Try pip install --user
                        let _ = Command::new(&python)
                            .arg("-m")
                            .arg("pip")
                            .arg("install")
                            .arg("--user")
                            .arg("fastapi")
                            .arg("uvicorn")
                            .arg("sqlalchemy")
                            .arg("pydantic")
                            .arg("pydantic-settings")
                            .arg("python-dotenv")
                            .arg("slowapi")
                            .arg("passlib")
                            .arg("bcrypt")
                            .arg("alembic")
                            .arg("openpyxl")
                            .arg("httpx")
                            .arg("python-jose")
                            .arg("python-multipart")
                            .current_dir(&bp)
                            .output();
                    }

                    // Start uvicorn with system Python — HIDDEN WINDOW on Windows
                    #[cfg(target_os = "windows")]
                    {
                        use std::os::windows::process::CommandExt;
                        const CREATE_NO_WINDOW: u32 = 0x08000000;

                        if let Ok(child) = Command::new(&python)
                            .arg("-m")
                            .arg("uvicorn")
                            .arg("main:app")
                            .arg("--host")
                            .arg(DEFAULT_HOST)
                            .arg("--port")
                            .arg(DEFAULT_PORT)
                            .creation_flags(CREATE_NO_WINDOW)
                            .current_dir(&bp)
                            .spawn()
                        {
                            *backend_child_setup.lock().unwrap() = Some(child);
                        }
                    }

                    #[cfg(not(target_os = "windows"))]
                    {
                        if let Ok(child) = Command::new(&python)
                            .arg("-m")
                            .arg("uvicorn")
                            .arg("main:app")
                            .arg("--host")
                            .arg(DEFAULT_HOST)
                            .arg("--port")
                            .arg(DEFAULT_PORT)
                            .current_dir(&bp)
                            .spawn()
                        {
                            *backend_child_setup.lock().unwrap() = Some(child);
                        }
                    }

                    println!("Backend Python started");
                    thread::sleep(Duration::from_secs(4));
                } else {
                    println!("Python not found. Please install Python 3.10+");
                }
            } else {
                println!("Backend not found in any location");
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_desktop_path,
            create_download_folder,
            save_file,
            get_mode,
            set_mode,
            get_server_ip,
            set_client_ip,
            get_lan_ip,
            test_connection,
        ])
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(mut child) = backend_child_cleanup.lock().unwrap().take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");

    // Final cleanup after Tauri exits (in case on_window_event didn't fire)
    if let Some(mut child) = backend_child.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    };
}

// ═══════════════════════════════════════════════════════════════════════
//  Existing Tauri Commands
// ═══════════════════════════════════════════════════════════════════════

#[tauri::command]
fn get_desktop_path() -> Result<String, String> {
    if let Some(user_dirs) = directories::UserDirs::new() {
        if let Some(desktop) = user_dirs.desktop_dir() {
            return Ok(desktop.to_string_lossy().to_string());
        }
    }
    Err("Could not find desktop directory".to_string())
}

#[tauri::command]
fn create_download_folder(folder_name: String) -> Result<String, String> {
    if let Some(user_dirs) = directories::UserDirs::new() {
        if let Some(desktop) = user_dirs.desktop_dir() {
            let folder_path = desktop.join(&folder_name);
            if !folder_path.exists() {
                std::fs::create_dir_all(&folder_path)
                    .map_err(|e| format!("Failed to create folder: {}", e))?;
            }
            return Ok(folder_path.to_string_lossy().to_string());
        }
    }
    Err("Could not find desktop directory".to_string())
}

#[tauri::command]
fn save_file(path: String, content: Vec<u8>) -> Result<(), String> {
    std::fs::write(&path, content).map_err(|e| format!("Failed to write file: {}", e))
}

// ═══════════════════════════════════════════════════════════════════════
//  LAN Mode Commands
// ═══════════════════════════════════════════════════════════════════════

/// Returns the current mode: "server" or "client".
/// Defaults to "server" when the store has no entry.
#[tauri::command]
fn get_mode(app: tauri::AppHandle) -> Result<String, String> {
    let store = app.store(STORE_PATH).map_err(|e| e.to_string())?;
    Ok(store
        .get("lan_mode")
        .and_then(|v| v.as_str().map(String::from))
        .unwrap_or_else(|| "server".to_string()))
}

/// Persists the mode ("server" or "client") to the store.
/// Callers should restart the app after switching modes.
#[tauri::command]
fn set_mode(mode: String, app: tauri::AppHandle) -> Result<(), String> {
    let store = app.store(STORE_PATH).map_err(|e| e.to_string())?;
    store.set("lan_mode".to_string(), json!(mode));
    store.save().map_err(|e| e.to_string())?;
    Ok(())
}

/// Returns the LAN IP detected at startup (server mode) or the stored
/// client IP (client mode).
#[tauri::command]
fn get_server_ip(
    state: tauri::State<'_, AppState>,
    app: tauri::AppHandle,
) -> Result<String, String> {
    let store = app.store(STORE_PATH).map_err(|e| e.to_string())?;
    let mode = store
        .get("lan_mode")
        .and_then(|v| v.as_str().map(String::from))
        .unwrap_or_else(|| "server".to_string());

    if mode == "client" {
        Ok(store
            .get("server_ip")
            .and_then(|v| v.as_str().map(String::from))
            .unwrap_or_else(|| "127.0.0.1".to_string()))
    } else {
        Ok(state.lan_ip.lock().unwrap().clone())
    }
}

/// Saves a client-side server IP address and sets mode to "client".
#[tauri::command]
fn set_client_ip(ip: String, app: tauri::AppHandle) -> Result<(), String> {
    let store = app.store(STORE_PATH).map_err(|e| e.to_string())?;
    store.set("server_ip".to_string(), json!(ip));
    store.set("lan_mode".to_string(), json!("client"));
    store.save().map_err(|e| e.to_string())?;
    Ok(())
}

/// Returns the LAN IP detected at app startup.
#[tauri::command]
fn get_lan_ip(state: tauri::State<'_, AppState>) -> Result<String, String> {
    Ok(state.lan_ip.lock().unwrap().clone())
}

/// Tests connectivity to a remote server by hitting its /health endpoint.
/// Returns `{ success: true, version: "..." }` or `{ success: false, error: "..." }`.
#[tauri::command]
async fn test_connection(ip: String) -> Result<serde_json::Value, String> {
    let url = format!("http://{}:{}/health", ip, DEFAULT_PORT);
    match reqwest::get(&url).await {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
            Ok(json!({
                "success": true,
                "version": body.get("version").and_then(|v| v.as_str()).unwrap_or("unknown"),
            }))
        }
        Err(e) => Ok(json!({
            "success": false,
            "error": e.to_string(),
        })),
    }
}
