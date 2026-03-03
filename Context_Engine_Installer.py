import sys
import os
import json
import shutil
import subprocess
import urllib.request
import re
import copy
from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtGui import QCloseEvent

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ==========================================
# 0. CONSENSUAL BOOTSTRAPPER & DEPENDENCY CHECK
# ==========================================
def ensure_dependencies():
    """
    Checks for PyQt6. 
    SECURITY: Asks for explicit user consent before installing anything via pip.
    """
    try:
        import PyQt6
        return
    except ImportError:
        pass

    print("\n" + "!"*60)
    print("MISSING DEPENDENCY: PyQt6")
    print("This script requires the PyQt6 GUI library to render the interface.")
    print("!"*60)
    
    response = input("Do you want to install PyQt6 via pip now? (y/n): ").strip().lower()
    if response != 'y':
        print("[!] User aborted. Exiting.")
        sys.exit(0)

    python_exe = sys.executable

    def run_pip_cmd(args):
        try:
            result = subprocess.run(
                [python_exe, "-m", "pip"] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                print(f"[!] Pip Error: {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"[!] Execution Exception: {e}")
            return False

    print("[*] Installing PyQt6...")
    if run_pip_cmd(["install", "PyQt6"]):
        print("[+] Installation success. Launching UI...")
    else:
        print("[!] Installation failed. Please check the logs above.")
        sys.exit(1)

ensure_dependencies()

# ==========================================
# IMPORTS
# ==========================================
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QCheckBox, QPushButton, QTextEdit, QMessageBox, QLabel, 
    QScrollArea, QFrame, QInputDialog, QLineEdit, QProgressBar, QTabWidget,
    QComboBox, QFileDialog, QDialog, QFormLayout, QDialogButtonBox,
    QSplitter, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QFont, QTextCursor, QPalette, QColor, QAction, QKeySequence
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QCoreApplication, QTimer

# ==========================================
# 1. CATALOGS
# ==========================================

AVAILABLE_SERVERS = {
    "semantic-brain": {
        "name": "Local RAG (mcp-local-rag)",
        "req": "npm",
        "config": {"command": "npx", "args": ["-y", "mcp-local-rag"], "env": {"BASE_DIR": "."}},
        "details": (
            "<b>Function:</b> Semantic Vector Search. Converts code into meaning-based mathematical embeddings.<br>"
            "<b>Token Cost:</b> <span style='color: #2E8B57;'>Highly Efficient.</span> Only sends perfectly matched snippets.<br>"
            "<b>Hardware:</b> Medium. Requires CPU spikes during the initial local indexing phase.<br>"
            "<b>Pro-Tip:</b> Best for massive, undocumented codebases. Zero API cost since embeddings run locally."
        )
    },
    "structural-map": {
        "name": "Code Index (code-index-mcp)",
        "req": "uv",
        "config": {"command": "uvx", "args": ["code-index-mcp"], "env": {}},
        "details": (
            "<b>Function:</b> AST Structural Search. Maps out exact function definitions, references, and class structures.<br>"
            "<b>Token Cost:</b> <span style='color: #2E8B57;'>Extremely Efficient.</span> Feeds the LLM exact function blocks without fluff.<br>"
            "<b>Hardware:</b> High CPU/RAM. AST parsing requires significant workstation power.<br>"
            "<b>Pro-Tip:</b> The absolute best tool for deep refactoring and tracing 'Go to Definition' usages."
        )
    },
    "memory-server": {
        "name": "Knowledge Memory",
        "req": "npm",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"], "env": {}},
        "details": (
            "<b>Function:</b> Persistent Brain. Acts as a local Knowledge Graph where the AI saves project rules.<br>"
            "<b>Token Cost:</b> <span style='color: #2E8B57;'>Very Low.</span> Only reads/writes short text nodes.<br>"
            "<b>Hardware:</b> Very Low. Runs easily on any machine.<br>"
            "<b>Pro-Tip:</b> Stops the AI from making the same mistakes twice or forgetting your preferred coding style."
        )
    },
    "filesystem": {
        "name": "Filesystem Access",
        "req": "npm",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."], "env": {}},
        "details": (
            "<b>Function:</b> Direct Drive Access. Grants the AI autonomous ability to explore, read, and write files.<br>"
            "<b>Token Cost:</b> <span style='color: #B22222;'>Variable/High.</span> Blind-searching burns through context windows.<br>"
            "<b>Warning:</b> <span style='color: #B22222;'>Gives the AI WRITE access.</span> Ensure you use Git to undo mistakes."
        )
    },
    "fetch": {
        "name": "Web Fetcher",
        "req": "npm",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"], "env": {}},
        "details": (
            "<b>Function:</b> Web Scraper. Converts external URLs into Markdown so the AI can read documentation.<br>"
            "<b>Token Cost:</b> <span style='color: #B22222;'>High.</span> Entire web pages are dumped into the prompt.<br>"
            "<b>Pro-Tip:</b> Essential when working with brand-new libraries that the LLM's base model wasn't trained on."
        )
    },
    "puppeteer": {
        "name": "Browser Automation (Puppeteer)",
        "req": "npm",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-puppeteer"], "env": {}},
        "details": (
            "<b>Function:</b> Headless Browser. The AI can physically click buttons, evaluate JavaScript, and scrape sites.<br>"
            "<b>Token Cost:</b> <span style='color: #DAA520;'>Medium/High.</span> Parsing the DOM consumes tokens.<br>"
            "<b>Hardware:</b> Medium. Requires downloading a background Chromium instance.<br>"
            "<b>Pro-Tip:</b> Incredible for having the AI write and test end-to-end UI automation."
        )
    },
    "sqlite": {
        "name": "SQLite Database Explorer",
        "req": "uv",
        "config": {"command": "uvx", "args": ["mcp-server-sqlite", "--db-path", "test.db"], "env": {}},
        "details": (
            "<b>Function:</b> Local DB Admin. Allows the AI to connect to `.db` files, map schemas, and run SQL queries.<br>"
            "<b>Token Cost:</b> <span style='color: #2E8B57;'>Low.</span> Only reads schemas and query outputs.<br>"
            "<b>Warning:</b> The AI can execute DROP, DELETE, and UPDATE queries. Use only on local development databases!"
        )
    },
    "github": {
        "name": "GitHub Integration",
        "req": "npm",
        "secure_prompt": True,
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": ""}},
        "details": (
            "<b>Function:</b> Repo Management. Connects to GitHub API to read issues, review PRs, and search remote repos.<br>"
            "<b>Token Cost:</b> <span style='color: #DAA520;'>Medium.</span> <br>"
            "<b>Setup Required:</b> The installer will securely prompt you for your GitHub Personal Access Token."
        )
    }
}

SUPPORTED_CLIENTS = {
    "opencode": {
        "name": "OpenCode Desktop",
        "paths": ["~/.config/opencode/opencode.json", "~/AppData/Roaming/opencode/config.json"]
    },
    "claude": {
        "name": "Claude Desktop",
        "paths": ["~/AppData/Roaming/Claude/claude_desktop_config.json", "~/Library/Application Support/Claude/claude_desktop_config.json"]
    },
    "windsurf": {
        "name": "Windsurf IDE",
        "paths": ["~/.codeium/windsurf/mcp_config.json"]
    },
    "continue_dev": {
        "name": "Continue.dev (VS Code / JetBrains)",
        "paths": ["~/.continue/config.json"]
    },
    "roo_code": {
        "name": "Roo Code / Cline (VS Code)",
        "paths": [
            "~/AppData/Roaming/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json",
            "~/Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json"
        ]
    },
    "zed": {
        "name": "Zed Editor",
        "paths": ["~/.config/zed/mcp.json", "~/AppData/Local/Zed/mcp.json"] 
    }
}

CUSTOM_SERVERS_FILE = "custom_servers.json"
CLIENT_PATHS_FILE = "client_paths.json"

# Load custom servers if they exist
if os.path.exists(CUSTOM_SERVERS_FILE):
    try:
        with open(CUSTOM_SERVERS_FILE, 'r') as f:
            custom_servers = json.load(f)
            for key, value in custom_servers.items():
                AVAILABLE_SERVERS[key] = value
    except Exception as e:
        print(f"Warning: Could not load custom servers: {e}")

# Load custom client paths if they exist
if os.path.exists(CLIENT_PATHS_FILE):
    try:
        with open(CLIENT_PATHS_FILE, 'r') as f:
            custom_clients = json.load(f)
            for key, value in custom_clients.items():
                SUPPORTED_CLIENTS[key] = value
    except Exception as e:
        print(f"Warning: Could not load custom client paths: {e}")

# ==========================================
# 2. BACKGROUND WORKER
# ==========================================
class InstallerWorker(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    server_status_signal = pyqtSignal(str, str)

    def __init__(self, servers_to_install, clients_to_target, catalog, dry_run=False):
        super().__init__()
        self.servers = servers_to_install
        self.clients = clients_to_target
        self.catalog = catalog
        self.dry_run = dry_run

    def get_actual_path(self, path_list):
        user_home = os.path.expanduser("~")
        for p in path_list:
            expanded = p.replace("~", user_home)
            if os.path.exists(expanded):
                return expanded
        return path_list[0].replace("~", user_home)

    def safe_load_json(self, file_path):
        if not os.path.exists(file_path):
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = re.sub(r'("(?:\\.|[^"\\])*")|//.*', lambda m: m.group(1) if m.group(1) else '', content)
            return json.loads(content)
        except Exception as e:
            self.log_signal.emit(f"[!] JSON Error in {os.path.basename(file_path)}: {e}")
            self.log_signal.emit("    -> Skipping this file to prevent data corruption.")
            return None

    def check_server_status(self, server_id):
        """Check if a server process is currently running"""
        try:
            if sys.platform == 'win32':
                result = subprocess.run(['tasklist', '/fi', f'imagename eq node.exe', '/fi', f'imagename eq uv.exe'], 
                                      capture_output=True, text=True)
                return "Running" if result.returncode == 0 else "Stopped"
            else:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                processes = result.stdout.lower()
                if 'npx' in processes or 'uvx' in processes:
                    return "Running"
                return "Stopped"
        except Exception:
            return "Unknown"

    def run(self):
        total_steps = len(self.clients) * 2 + len(self.clients)
        current_step = 0

        for client_id, client_data in self.clients.items():
            self.log_signal.emit(f"\n[*] Processing Client: {client_data['name']}")
            target_path = self.get_actual_path(client_data["paths"])
            self.log_signal.emit(f"    Target File: {target_path}")

            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
            except OSError as e:
                self.error_signal.emit(f"Permission denied creating directory: {e}")
                continue

            config_data = self.safe_load_json(target_path)
            if config_data is None: 
                continue

            # Update server status
            for srv_id in self.servers:
                status = self.check_server_status(srv_id)
                self.server_status_signal.emit(srv_id, status)

            if not self.dry_run:
                backup_path = f"{target_path}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                try:
                    shutil.copy2(target_path, backup_path)
                    self.log_signal.emit(f"    [+] Backup created: {os.path.basename(backup_path)}")
                except Exception as e:
                    self.error_signal.emit(f"Failed to create backup: {e}")
                    continue

            if "mcpServers" not in config_data:
                config_data["mcpServers"] = {}

            for srv_id in self.catalog:
                if srv_id in config_data["mcpServers"] and srv_id not in self.servers:
                    if not self.dry_run:
                        del config_data["mcpServers"][srv_id]
                    self.log_signal.emit(f"    [-] Uninstalled: {srv_id}")

            for srv_id, srv_data in self.servers.items():
                if not self.dry_run:
                    srv_config = copy.deepcopy(srv_data["config"])
                    config_data["mcpServers"][srv_id] = srv_config
                self.log_signal.emit(f"    [+] Installed/Updated: {srv_id}")

            if not self.dry_run:
                try:
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, indent=2)
                    self.log_signal.emit(f"    [SUCCESS] Configuration synced.")
                except Exception as e:
                    self.error_signal.emit(f"Write error: {e}")

            current_step += 1
            self.progress_signal.emit(int((current_step / total_steps) * 100))

        self.finished_signal.emit()


# ==========================================
# 3. UI CLASSES
# ==========================================

class PreviewDialog(QDialog):
    def __init__(self, servers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration Preview")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        label = QLabel("Configuration that will be written:")
        label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(label)
        
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet("background-color: #1E1E1E; color: #4AF626; font-family: Consolas;")
        
        config = {"mcpServers": {}}
        for srv_id, srv_data in servers.items():
            config["mcpServers"][srv_id] = srv_data["config"]
        
        self.preview.setPlainText(json.dumps(config, indent=2))
        layout.addWidget(self.preview)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


class CustomServerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Server")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.command_edit = QLineEdit()
        self.args_edit = QLineEdit()
        self.env_edit = QLineEdit()
        self.req_combo = QComboBox()
        self.req_combo.addItems(["npm", "uv"])
        
        form.addRow("Server Name:", self.name_edit)
        form.addRow("Command:", self.command_edit)
        form.addRow("Arguments (comma-separated):", self.args_edit)
        form.addRow("Environment (key=value, comma-separated):", self.env_edit)
        form.addRow("Requires:", self.req_combo)
        
        layout.addLayout(form)
        
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "req": self.req_combo.currentText(),
            "config": {
                "command": self.command_edit.text(),
                "args": [a.strip() for a in self.args_edit.text().split(',') if a.strip()],
                "env": dict(item.split('=') for item in self.env_edit.text().split(',') if '=' in item)
            }
        }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultimate MCP Context Engine Installer")
        self.resize(1200, 800)
        
        self.server_checkboxes = {}
        self.client_checkboxes = {}
        self.server_status = {}
        self.worker = None
        self._thread = None
        
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Header
        lbl_header = QLabel("Context Engine Setup & Sync")
        lbl_header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(lbl_header)

        # Toolbar
        toolbar = QHBoxLayout()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search servers...")
        self.search_edit.textChanged.connect(self.filter_servers)
        
        btn_refresh = QPushButton("Refresh Status")
        btn_refresh.clicked.connect(self.refresh_statuses)
        
        btn_custom = QPushButton("Add Custom Server")
        btn_custom.clicked.connect(self.add_custom_server)
        
        btn_export = QPushButton("Export Settings")
        btn_export.clicked.connect(self.export_settings)
        
        btn_import = QPushButton("Import Settings")
        btn_import.clicked.connect(self.import_settings)
        
        toolbar.addWidget(self.search_edit)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_custom)
        toolbar.addWidget(btn_export)
        toolbar.addWidget(btn_import)
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)

        # Split View
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # LEFT: Servers
        grp_srv = QGroupBox("1. Select Context Engines (Servers)")
        grp_srv.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        v_srv = QVBoxLayout()
        
        scroll_srv = QScrollArea()
        scroll_srv.setWidgetResizable(True)
        scroll_srv.setFrameShape(QFrame.Shape.NoFrame)
        
        wid_srv = QWidget()
        lay_srv = QVBoxLayout(wid_srv)
        lay_srv.setSpacing(10)
        
        for k, v in AVAILABLE_SERVERS.items():
            box = QGroupBox()
            box.setStyleSheet("QGroupBox { border: 1px solid #444; border-radius: 5px; margin-top: 5px; }")
            box_l = QVBoxLayout()
            
            cb = QCheckBox(f"{v['name']}")
            cb.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.server_checkboxes[k] = cb
            cb.stateChanged.connect(lambda state, id=k: self.update_status(id, state))
            
            req_lbl = QLabel(f"Requires: {v['req']}")
            req_lbl.setStyleSheet("color: #AAA; font-weight: bold; font-size: 10px;")
            
            status_lbl = QLabel("Status: Unknown")
            status_lbl.setStyleSheet("color: #888; font-size: 9px;")
            self.server_status[k] = status_lbl
            
            desc = QLabel(v['details'])
            desc.setTextFormat(Qt.TextFormat.RichText)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #CCC; margin-top: 5px;")
            
            box_l.addWidget(cb)
            box_l.addWidget(req_lbl)
            box_l.addWidget(status_lbl)
            box_l.addWidget(desc)
            box.setLayout(box_l)
            lay_srv.addWidget(box)
            
        lay_srv.addStretch()
        scroll_srv.setWidget(wid_srv)
        v_srv.addWidget(scroll_srv)
        grp_srv.setLayout(v_srv)
        splitter.addWidget(grp_srv)

        # RIGHT: Clients
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        grp_cli = QGroupBox("2. Target Software (Clients)")
        grp_cli.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        v_cli = QVBoxLayout()
        
        scroll_cli = QScrollArea()
        scroll_cli.setWidgetResizable(True)
        scroll_cli.setFrameShape(QFrame.Shape.NoFrame)
        
        wid_cli = QWidget()
        lay_cli = QVBoxLayout(wid_cli)
        lay_cli.setSpacing(10)

        for k, v in SUPPORTED_CLIENTS.items():
            cb = QCheckBox(v['name'])
            cb.setFont(QFont("Segoe UI", 11))
            self.client_checkboxes[k] = cb
            lay_cli.addWidget(cb)
            
        lay_cli.addStretch()
        scroll_cli.setWidget(wid_cli)
        v_cli.addWidget(scroll_cli)
        grp_cli.setLayout(v_cli)
        right_layout.addWidget(grp_cli)
        
        # Buttons
        btn_preview = QPushButton("Preview Configuration")
        btn_preview.clicked.connect(self.show_preview)
        
        btn_dry_run = QPushButton("Dry Run")
        btn_dry_run.clicked.connect(self.start_dry_run)
        
        btn_rollback = QPushButton("Rollback (Restore Last Backup)")
        btn_rollback.clicked.connect(self.rollback_config)
        
        btn_check = QPushButton("Detect Installed Clients")
        btn_check.clicked.connect(self.detect_installed_clients)
        
        right_layout.addWidget(btn_preview)
        right_layout.addWidget(btn_dry_run)
        right_layout.addWidget(btn_rollback)
        right_layout.addWidget(btn_check)
        right_layout.addStretch()
        
        splitter.addWidget(right_panel)
        main_layout.addWidget(splitter)

        # Progress Bar
        self.progress = QProgressBar()
        self.progress.hide()
        main_layout.addWidget(self.progress)

        # Sync Button
        self.btn_run = QPushButton("Sync Configuration (Install / Remove)")
        self.btn_run.setMinimumHeight(60)
        self.btn_run.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_run.setStyleSheet("background-color: #007ACC; color: white; border-radius: 5px;")
        self.btn_run.clicked.connect(self.start_process)
        main_layout.addWidget(self.btn_run)

        # Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(180)
        self.console.setStyleSheet("background-color: #1E1E1E; color: #4AF626; font-family: Consolas; border-radius: 5px;")
        main_layout.addWidget(self.console)

        self.log("System initialized. Select items and click Sync.")

    def filter_servers(self, text):
        text = text.lower()
        for k, cb in self.server_checkboxes.items():
            server_name = AVAILABLE_SERVERS[k]['name'].lower()
            cb.setVisible(text in server_name)

    def update_status(self, server_id, state):
        if state == Qt.CheckState.Checked.value:
            self.console.append(f"[Info] Selected: {AVAILABLE_SERVERS[server_id]['name']}")

    def refresh_statuses(self):
        self.log("[*] Checking server statuses...")
        for k in self.server_checkboxes:
            status = self.check_server_status(k)
            if k in self.server_status:
                self.server_status[k].setText(f"Status: {status}")
                self.server_status[k].setStyleSheet("color: #2E8B57; font-size: 9px;" if status == "Running" else "color: #B22222; font-size: 9px;")

    def check_server_status(self, server_id):
        try:
            if sys.platform == 'win32':
                result = subprocess.run(['tasklist'], capture_output=True, text=True)
                return "Running" if result.returncode == 0 else "Stopped"
            else:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                return "Running" if result.returncode == 0 else "Stopped"
        except Exception:
            return "Unknown"

    def add_custom_server(self):
        dialog = CustomServerDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            name = data['name'].lower().replace(' ', '-').replace('_', '-')
            new_id = f"custom-{name}"
            if len(new_id) > 30:
                new_id = new_id[:30]
            
            AVAILABLE_SERVERS[new_id] = {
                "name": data['name'],
                "req": data['req'],
                "config": data['config'],
                "details": "<b>Custom Server</b>"
            }
            
            self.server_checkboxes[new_id] = None
            
            QMessageBox.information(self, "Success", f"Custom server '{data['name']}' added!")
            self.log(f"[+] Added custom server: {data['name']}")

    def export_settings(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export Settings", "", "JSON Files (*.json)")
        if filename:
            settings = {
                "servers": [k for k, cb in self.server_checkboxes.items() if cb.isChecked()],
                "clients": [k for k, cb in self.client_checkboxes.items() if cb.isChecked()],
                "timestamp": datetime.now().isoformat()
            }
            with open(filename, 'w') as f:
                json.dump(settings, f, indent=2)
            self.log(f"[+] Settings exported to {filename}")

    def import_settings(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import Settings", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'r') as f:
                    settings = json.load(f)
                
                for k, cb in self.server_checkboxes.items():
                    if k in settings.get('servers', []):
                        cb.setChecked(True)
                
                for k, cb in self.client_checkboxes.items():
                    if k in settings.get('clients', []):
                        cb.setChecked(True)
                
                self.log(f"[+] Settings imported from {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import settings: {e}")

    def show_preview(self):
        sel_servers = {k: AVAILABLE_SERVERS[k] for k, cb in self.server_checkboxes.items() if cb.isChecked()}
        if not sel_servers:
            QMessageBox.warning(self, "Warning", "No servers selected.")
            return
        dialog = PreviewDialog(sel_servers, self)
        dialog.exec()

    def detect_installed_clients(self):
        self.log("[*] Detecting installed clients...")
        for k, client_data in SUPPORTED_CLIENTS.items():
            for path in client_data['paths']:
                expanded = path.replace("~", os.path.expanduser("~"))
                if os.path.exists(expanded):
                    if k in self.client_checkboxes:
                        self.client_checkboxes[k].setChecked(True)
                        self.log(f"    Found: {client_data['name']} at {expanded}")

    def rollback_config(self):
        backups = []
        user_home = os.path.expanduser("~")
        
        for k, client_data in SUPPORTED_CLIENTS.items():
            for path in client_data['paths']:
                expanded = path.replace("~", user_home)
                backup_path = f"{expanded}.*.bak"
                matching = [f for f in os.listdir(os.path.dirname(expanded)) 
                           if f.startswith(os.path.basename(expanded) + '.') and f.endswith('.bak')]
                if matching:
                    backups.extend([os.path.join(os.path.dirname(expanded), f) for f in matching])
        
        if not backups:
            QMessageBox.information(self, "Rollback", "No backup files found.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Backup to Restore")
        layout = QVBoxLayout(dialog)
        
        list_widget = QListWidget()
        for b in backups:
            list_widget.addItem(QListWidgetItem(b))
        
        layout.addWidget(list_widget)
        
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec():
            selected = list_widget.selectedItems()
            if selected:
                backup_file = selected[0].text()
                target = backup_file.rsplit('.', 2)[0]
                try:
                    shutil.copy2(backup_file, target)
                    self.log(f"[+] Restored from backup: {backup_file}")
                    QMessageBox.information(self, "Success", f"Configuration restored from {backup_file}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to restore: {e}")

    def log(self, msg):
        self.console.append(msg)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def check_tool_availability(self, tool_name):
        if tool_name == "npm":
            return shutil.which("npm") is not None
        if tool_name == "uv":
            return shutil.which("uv") is not None
        return False

    def get_secure_input(self, title, label):
        text, ok = QInputDialog.getText(self, title, label, QLineEdit.EchoMode.Password)
        return text.strip() if ok else None

    def start_process(self, dry_run=False):
        self.console.clear()
        
        sel_servers = {k: AVAILABLE_SERVERS[k] for k, cb in self.server_checkboxes.items() if cb.isChecked()}
        sel_clients = {k: SUPPORTED_CLIENTS[k] for k, cb in self.client_checkboxes.items() if cb.isChecked()}

        if not sel_clients:
            QMessageBox.warning(self, "Error", "Please select at least one Target Client software.")
            return

        reqs = set(s['req'] for s in sel_servers.values())
        missing = [r for r in reqs if not self.check_tool_availability(r)]
        
        if missing:
            msg = f"You are missing the following required tools:\n\n{', '.join(missing)}\n\nPlease install them and ensure they are in your system PATH."
            QMessageBox.critical(self, "Missing Prerequisites", msg)
            return

        for k, s in sel_servers.items():
            if s.get("secure_prompt"):
                token = self.get_secure_input(f"Setup {s['name']}", f"Enter API Token for {s['name']}:")
                if not token:
                    self.log(f"[!] Skipped {s['name']} (No token provided by user)")
                    del sel_servers[k] 
                else:
                    s_config = copy.deepcopy(s["config"])
                    s_config["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] = token
                    sel_servers[k] = copy.deepcopy(s)
                    sel_servers[k]["config"] = s_config

        self._thread = QThread()
        self.worker = InstallerWorker(sel_servers, sel_clients, AVAILABLE_SERVERS, dry_run=dry_run)
        self.worker.moveToThread(self._thread)
        self.worker.finished_signal.connect(self._thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self.worker.log_signal.connect(self.log)
        self.worker.error_signal.connect(lambda err: QMessageBox.critical(self, "Error", err))
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.server_status_signal.connect(self.update_server_status)
        self._thread.finished.connect(lambda: self.btn_run.setEnabled(True))
        self._thread.finished.connect(lambda: self.progress.hide())
        
        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        
        self._thread.started.connect(self.worker.run)
        self._thread.start()

    def update_server_status(self, server_id, status):
        if server_id in self.server_status:
            color = "#2E8B57" if status == "Running" else "#B22222"
            self.server_status[server_id].setText(f"Status: {status}")
            self.server_status[server_id].setStyleSheet(f"color: {color}; font-size: 9px;")

    def start_dry_run(self):
        self.start_process(dry_run=True)
        self.log("[*] DRY RUN: No changes will be written to disk.")

    def closeEvent(self, a0: QCloseEvent | None):
        try:
            with open(CUSTOM_SERVERS_FILE, 'w') as f:
                custom = {k: v for k, v in AVAILABLE_SERVERS.items() if k.startswith('custom-')}
                json.dump(custom, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save custom servers: {e}")
        if a0 is not None:
            super().closeEvent(a0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    p = app.palette()
    p.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
    p.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.black)
    p.setColor(QPalette.ColorRole.AlternateBase, Qt.GlobalColor.darkGray)
    p.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.Button, Qt.GlobalColor.darkGray)
    p.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link, Qt.GlobalColor.cyan)
    p.setColor(QPalette.ColorRole.Highlight, Qt.GlobalColor.cyan)
    p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(p)
    
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
