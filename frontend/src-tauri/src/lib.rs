use std::sync::Mutex;
use std::process::Child;
use std::path::PathBuf;
use std::env;

static DJANGO_PROCESS: Mutex<Option<Child>> = Mutex::new(None);

fn find_django_paths() -> Option<(PathBuf, PathBuf)> {
  let mut current_dir = env::current_dir().ok()?;
  for _ in 0..5 {
    let manage_py = current_dir.join("manage.py");
    if manage_py.exists() {
      let venv_python = if cfg!(windows) {
        current_dir.join(".venv").join("Scripts").join("python.exe")
      } else {
        current_dir.join(".venv").join("bin").join("python")
      };

      let python_exe = if venv_python.exists() {
        venv_python
      } else {
        PathBuf::from(if cfg!(windows) { "python" } else { "python3" })
      };
      return Some((python_exe, manage_py));
    }
    if let Some(parent) = current_dir.parent() {
      current_dir = parent.to_path_buf();
    } else {
      break;
    }
  }
  None
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let app = tauri::Builder::default()
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }

      if let Some((python_path, manage_path)) = find_django_paths() {
        let mut command = std::process::Command::new(python_path);
        command.arg(&manage_path);
        command.arg("runserver");
        command.arg("127.0.0.1:8000");
        command.arg("--noreload");

        if let Some(parent) = manage_path.parent() {
          command.current_dir(parent);
        }

        command.stdout(std::process::Stdio::inherit());
        command.stderr(std::process::Stdio::inherit());

        match command.spawn() {
          Ok(child) => {
            println!("Successfully spawned Django server sidecar");
            *DJANGO_PROCESS.lock().unwrap() = Some(child);
          }
          Err(e) => {
            eprintln!("Failed to spawn Django server sidecar: {}", e);
          }
        }
      } else {
        eprintln!("Failed to find Django paths for sidecar execution");
      }

      Ok(())
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application");

  app.run(|_app_handle, event| match event {
    tauri::RunEvent::Exit => {
      if let Ok(mut guard) = DJANGO_PROCESS.lock() {
        if let Some(mut child) = guard.take() {
          println!("Terminating Django sidecar process...");
          let _ = child.kill();
        }
      }
    }
    _ => {}
  });
}
