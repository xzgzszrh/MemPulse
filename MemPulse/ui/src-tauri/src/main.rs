#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::{io::{BufRead, BufReader, Write}, process::{Child, ChildStdin, ChildStdout, Command, Stdio}, sync::{Arc, Mutex}};
use tauri::{Manager, RunEvent};

struct Backend { child: Child, input: ChildStdin, output: BufReader<ChildStdout> }
impl Backend {
    fn request(&mut self, request: serde_json::Value) -> Result<serde_json::Value, String> {
        writeln!(self.input, "{}", request).map_err(|e| format!("本地服务写入失败：{e}"))?;
        self.input.flush().map_err(|e| e.to_string())?;
        let mut line = String::new();
        if self.output.read_line(&mut line).map_err(|e| e.to_string())? == 0 {
            return Err("本地记忆服务已退出，请重新启动应用。".into());
        }
        let response: serde_json::Value = serde_json::from_str(&line).map_err(|e| e.to_string())?;
        if response["ok"] == true { Ok(response["data"].clone()) }
        else { Err(response["error"].as_str().unwrap_or("本地服务请求失败").into()) }
    }
}
impl Drop for Backend {
    fn drop(&mut self) { let _ = self.child.kill(); let _ = self.child.wait(); }
}
type SharedBackend = Arc<Mutex<Backend>>;

#[tauri::command]
async fn memory_request(state: tauri::State<'_, SharedBackend>, method: String, params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    let backend = state.inner().clone();
    // Blocking pipe I/O never runs on the window event loop. Requests are serialized
    // through the same facade/SQLite connection; stdout is reserved for JSON lines.
    tauri::async_runtime::spawn_blocking(move || {
        backend.lock().map_err(|e| e.to_string())?.request(serde_json::json!({"method": method, "params": params}))
    }).await.map_err(|e| e.to_string())?
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            let mut command = if cfg!(debug_assertions) {
                let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
                let python = root.join(".venv/bin/python");
                let python = if python.exists() { python } else { std::path::PathBuf::from("python3") };
                let mut cmd = Command::new(python);
                cmd.arg(root.join("scripts/desktop_entry.py"));
                cmd
            } else {
                Command::new(std::env::current_exe()?.parent().unwrap().join(if cfg!(target_os="windows") { "mempulse-service.exe" } else { "mempulse-service" }))
            };
            command.arg("--data-dir").arg(data_dir).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::inherit());
            #[cfg(target_os="windows")]
            { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
            let mut child = command.spawn()?;
            let input = child.stdin.take().ok_or("无法连接本地服务输入")?;
            let output = BufReader::new(child.stdout.take().ok_or("无法连接本地服务输出")?);
            app.manage(Arc::new(Mutex::new(Backend { child, input, output })));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![memory_request])
        .build(tauri::generate_context!()).expect("无法启动 MemPulse 桌面应用");
    app.run(|handle, event| {
        if matches!(event, RunEvent::Exit) {
            if let Some(backend) = handle.try_state::<SharedBackend>() {
                if let Ok(mut service) = backend.lock() { let _ = service.child.kill(); let _ = service.child.wait(); }
            }
        }
    });
}
