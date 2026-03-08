import sys
import os
import json
import shutil
import subprocess
import re
import copy
from datetime import datetime

from PySide6.QtGui import QCloseEvent

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
    Checks for PySide6. 
    SECURITY: Asks for explicit user consent before installing anything via pip.
    """
    try:
        import PySide6
        return
    except ImportError:
        pass

    print("\n" + "!"*60)
    print("MISSING DEPENDENCY: PySide6")
    print("This script requires the PySide6 GUI library to render the interface.")
    print("!"*60)
    
    response = input("Do you want to install PySide6 via pip now? (y/n): ").strip().lower()
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

    print("[*] Installing PySide6...")
    if run_pip_cmd(["install", "PySide6"]):
        print("[+] Installation success. Launching UI...")
    else:
        print("[!] Installation failed. Please check the logs above.")
        sys.exit(1)

ensure_dependencies()

# ==========================================
# IMPORTS
# ==========================================
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QCheckBox, QPushButton, QTextEdit, QMessageBox, QLabel, 
    QScrollArea, QFrame, QInputDialog, QLineEdit, QProgressBar, QTabWidget,
    QComboBox, QFileDialog, QDialog, QFormLayout, QDialogButtonBox,
    QSplitter, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QFont, QTextCursor, QPalette, QColor, QAction, QKeySequence
from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QObject, QCoreApplication, QTimer

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
        "paths": ["~/.config/opencode/opencode.json", "~/AppData/Roaming/opencode/config.json"],
        "skills_path": "~/.config/opencode/skills/"
    },
    "claude": {
        "name": "Claude Desktop",
        "paths": ["~/AppData/Roaming/Claude/claude_desktop_config.json", "~/Library/Application Support/Claude/claude_desktop_config.json"],
        "skills_path": "~/.claude/skills/"
    },
    "windsurf": {
        "name": "Windsurf IDE",
        "paths": ["~/.codeium/windsurf/mcp_config.json"],
        "skills_path": "~/.windsurf/skills/"
    },
    "continue_dev": {
        "name": "Continue.dev (VS Code / JetBrains)",
        "paths": ["~/.continue/config.json"],
        "skills_path": None
    },
    "roo_code": {
        "name": "Roo Code / Cline (VS Code)",
        "paths": [
            "~/AppData/Roaming/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json",
            "~/Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json"
        ],
        "skills_path": "~/.cline/skills/"
    },
    "zed": {
        "name": "Zed Editor",
        "paths": ["~/.config/zed/mcp.json", "~/AppData/Local/Zed/mcp.json"],
        "skills_path": None
    }
}

AVAILABLE_SKILLS = {
    "ui-ux-pro-max": {
        "name": "UI/UX Pro Max",
        "description": "Frontend UI/UX with searchable palettes, typography, and stack guidelines for React, Next.js, Vue, Tailwind, etc.",
        "repo": "jmerta/codex-skills",
        "folder": "ui-ux-pro-max",
        "details": (
            "<b>Category:</b> Frontend Design<br>"
            "<b>Use for:</b> Creating stunning UI/UX with searchable style databases, color palettes, font pairings, and component guidelines."
        )
    },
    "frontend-ui-ux": {
        "name": "Frontend UI/UX",
        "description": "Designer-turned-developer for creating stunning UI without design mockups. Focuses on spacing, color harmony, and micro-interactions.",
        "repo": "code-yeongyu/oh-my-opencode",
        "folder": "src/features/builtin-skills/frontend-ui-ux",
        "details": (
            "<b>Category:</b> Frontend Design<br>"
            "<b>Use for:</b> Pixel-perfect interfaces, smooth animations, and intuitive interactions without mockups."
        )
    },
    "fastapi": {
        "name": "FastAPI Backend",
        "description": "Production-ready FastAPI services with asyncio, proper validation, and efficient dependency patterns.",
        "repo": "openclaw/skills",
        "folder": "fastapi",
        "details": (
            "<b>Category:</b> Python Backend<br>"
            "<b>Use for:</b> Building scalable APIs with FastAPI, Pydantic validation, and async patterns."
        )
    },
    "python-testing-patterns": {
        "name": "Python Testing Patterns",
        "description": "Robust pytest testing with fixtures, mocks, and best practices for reliable unit and integration tests.",
        "repo": "nickcrew/claude-cortex",
        "folder": "python-testing-patterns",
        "details": (
            "<b>Category:</b> Testing<br>"
            "<b>Use for:</b> Writing maintainable pytest tests with proper fixtures, mocking, and edge case coverage."
        )
    },
    "git": {
        "name": "Git Version Control",
        "description": "Full version control with branching strategies, collaboration workflows, and conflict resolution.",
        "repo": "openclaw/skills",
        "folder": "git",
        "details": (
            "<b>Category:</b> DevOps<br>"
            "<b>Use for:</b> Git workflows, atomic commits, branch management, and collaboration."
        )
    },
    "security-review": {
        "name": "Security Review",
        "description": "Comprehensive security analysis detecting OWASP issues, hardcoded secrets, and insecure coding patterns.",
        "repo": "yeachan-heo/oh-my-claudecode",
        "folder": "security-review",
        "details": (
            "<b>Category:</b> Security<br>"
            "<b>Use for:</b> Security audits, vulnerability detection, and secure coding best practices."
        )
    },
    "databases": {
        "name": "Database Design",
        "description": "Design schemas, optimize queries, and manage migrations for MongoDB and PostgreSQL.",
        "repo": "mamba-mental/agent-skill-manager",
        "folder": "databases",
        "details": (
            "<b>Category:</b> Database<br>"
            "<b>Use for:</b> Database schema design, query optimization, and migration management."
        )
    },
    "docker-compose-generator": {
        "name": "Docker Compose Generator",
        "description": "Generate ready-to-use docker-compose.yml for common services like MySQL, Redis, MongoDB, and more.",
        "repo": "openclaw/skills",
        "folder": "docker-compose-generator",
        "details": (
            "<b>Category:</b> DevOps<br>"
            "<b>Use for:</b> Quick local development environments with Docker Compose."
        )
    }
}

CUSTOM_SERVERS_FILE = "custom_servers.json"
CLIENT_PATHS_FILE = "client_paths.json"

def load_custom_files():
    if os.path.exists(CUSTOM_SERVERS_FILE):
        try:
            with open(CUSTOM_SERVERS_FILE, 'r') as f:
                custom_servers = json.load(f)
                for key, value in custom_servers.items():
                    AVAILABLE_SERVERS[key] = value
        except Exception as e:
            print(f"Warning: Could not load custom servers: {e}")

    if os.path.exists(CLIENT_PATHS_FILE):
        try:
            with open(CLIENT_PATHS_FILE, 'r') as f:
                custom_clients = json.load(f)
                for key, value in custom_clients.items():
                    SUPPORTED_CLIENTS[key] = value
        except Exception as e:
            print(f"Warning: Could not load custom client paths: {e}")

load_custom_files()

# ==========================================
# 2. BACKGROUND WORKER
# ==========================================
class InstallerWorker(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    server_status_signal = pyqtSignal(str, str)
    
    # Alias for backward compatibility
    signal = pyqtSignal

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
        return None

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
        try:
            if sys.platform == 'win32':
                result = subprocess.run(['tasklist'], capture_output=True, text=True)
                return "Running" if result.stdout.lower().strip() else "Stopped"
            else:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                return "Running" if result.stdout.strip() else "Stopped"
        except Exception:
            return "Unknown"

    def run(self):
        total_steps = len(self.clients) * (2 + len(self.servers))
        current_step = 0

        for client_id, client_data in self.clients.items():
            self.log_signal.emit(f"\n[*] Processing Client: {client_data['name']}")
            target_path = self.get_actual_path(client_data["paths"])
            if target_path is None:
                self.error_signal.emit(f"    [!] No valid config path found for {client_data['name']}")
                continue
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
            for srv_id in self.catalog:
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

            for srv_id in list(config_data["mcpServers"].keys()):
                if srv_id not in self.servers:
                    if not self.dry_run:
                        del config_data["mcpServers"][srv_id]
                        self.log_signal.emit(f"    [-] Uninstalled: {srv_id}")

            for srv_id, srv_data in self.servers.items():
                if not self.dry_run:
                    config_data["mcpServers"][srv_id] = copy.deepcopy(srv_data["config"])
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
            if srv_data.get("secure_prompt"):
                srv_config = {"command": srv_data["config"]["command"], "args": srv_data["config"]["args"], "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "<TOKEN_PROMPTED>"}}
            else:
                srv_config = srv_data["config"]
            config["mcpServers"][srv_id] = srv_config
        
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


class MCPMarketBrowserDialog(QDialog):
    """MCP Market Browser with tabs for Servers and Skills"""
    
    def __init__(self, parent=None, default_tab='servers'):
        super().__init__(parent)
        self.setWindowTitle("MCP Market Browser")
        self.resize(800, 600)
        
        self.servers = []
        self.skills = []
        self.selected_servers = []
        self.selected_skills = []
        
        layout = QVBoxLayout(self)
        
        # Search and Sort
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self.filter_results)
        search_layout.addWidget(self.search_input)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Stars (High to Low)", "Stars (Low to High)", "Name (A-Z)", "Name (Z-A)", "Newest"])
        self.sort_combo.currentTextChanged.connect(self.sort_results)
        search_layout.addWidget(QLabel("Sort:"))
        search_layout.addWidget(self.sort_combo)
        
        layout.addLayout(search_layout)
        
        # Tabs
        self.tabs = QTabWidget()
        
        # Servers Tab
        self.servers_list = QListWidget()
        self.servers_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.tabs.addTab(self.servers_list, "MCP Servers")
        
        # Skills Tab
        self.skills_list = QListWidget()
        self.skills_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.tabs.addTab(self.skills_list, "Skills")
        
        if default_tab == 'servers':
            self.tabs.setCurrentIndex(0)
        elif default_tab == 'skills':
            self.tabs.setCurrentIndex(1)
        
        layout.addWidget(self.tabs)
        
        # Client Selection
        client_layout = QHBoxLayout()
        client_layout.addWidget(QLabel("Install to:"))
        self.client_checks = {}
        for k, v in SUPPORTED_CLIENTS.items():
            if v.get('skills_path'):
                cb = QCheckBox(v['name'])
                self.client_checks[k] = cb
                client_layout.addWidget(cb)
        client_layout.addStretch()
        layout.addLayout(client_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load from MCP Market")
        self.btn_load.clicked.connect(self.load_from_market)
        btn_layout.addWidget(self.btn_load)
        
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_install = QPushButton("Install Selected")
        self.btn_install.setStyleSheet("background-color: #28a745; color: white;")
        self.btn_install.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_install)
        
        layout.addLayout(btn_layout)
        
        self.status_label = QLabel("Click 'Load from MCP Market' to fetch servers and skills")
        layout.addWidget(self.status_label)
    
    def load_from_market(self):
        self.status_label.setText("Loading from MCP Market...")
        self.btn_load.setEnabled(False)
        QApplication.processEvents()
        
        # Load servers
        self.load_servers()
        
        # Load skills
        self.load_skills()
        
        self.status_label.setText(f"Loaded {len(self.servers)} servers and {len(self.skills)} skills")
        self.btn_load.setEnabled(True)
    
    def load_servers(self):
        try:
            result = subprocess.run(
                ['npx', '-y', '@mcpmarket/mcp-auto-install', 'list'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                import json
                try:
                    data = json.loads(result.stdout)
                    for item in data:
                        self.servers.append({
                            'name': item.get('name', 'Unknown'),
                            'description': item.get('description', ''),
                            'command': item.get('command', ''),
                            'stars': item.get('stars', 0)
                        })
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            self.status_label.setText(f"Error loading servers: {e}")
        
        self.populate_servers_list()
    
    def load_skills(self):
        try:
            result = subprocess.run(
                ['npx', '-y', 'skillfish', 'search', '--json'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                import json
                try:
                    data = json.loads(result.stdout)
                    for item in data:
                        self.skills.append({
                            'name': item.get('name', 'Unknown'),
                            'description': item.get('description', ''),
                            'repo': item.get('repo', ''),
                            'stars': item.get('stars', 0)
                        })
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        
        if not self.skills:
            self.skills = [
                {'name': 'React Code Fix & Linter', 'description': 'Automates code formatting and linting', 'repo': 'facebook/react-code-fix-linter', 'stars': 242682},
                {'name': 'GitHub Integration', 'description': 'Manages PRs, issues, CI/CD', 'repo': 'openclaw/github-integration', 'stars': 228576},
                {'name': 'Coding Agent Orchestrator', 'description': 'Delegates tasks to AI agents', 'repo': 'openclaw/coding-agent-orchestrator', 'stars': 228567},
                {'name': 'Google Workspace CLI', 'description': 'Gmail, Calendar, Drive integration', 'repo': 'openclaw/google-workspace-cli', 'stars': 228567},
                {'name': 'n8n Pull Request Creator', 'description': 'Auto-creates GitHub PRs', 'repo': 'n8n-io/n8n-pull-request-creator', 'stars': 170914},
                {'name': 'Uv Python Tool Installer', 'description': 'Install Python tools with uv', 'repo': 'aresbit/uv-python-tool-installer', 'stars': 50000},
                {'name': 'Codex Root Cause Fixer', 'description': 'Diagnoses and fixes errors', 'repo': 'phrazzld/codex-root-cause-fixer', 'stars': 45000},
                {'name': 'Strict TDD Workflow', 'description': 'Test-driven development process', 'repo': 'humansintheloop-dev/strict-tdd-workflow', 'stars': 40000},
            ]
        
        self.populate_skills_list()
    
    def populate_servers_list(self):
        self.servers_list.clear()
        for s in self.servers:
            item = QListWidgetItem()
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            name = QLabel(f"● {s['name']}")
            name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            
            desc = QLabel(s['description'][:80] + "..." if len(s['description']) > 80 else s['description'])
            desc.setStyleSheet("color: #888; font-size: 9px;")
            
            cmd = QLabel(f"📦 {s['command']}")
            cmd.setStyleSheet("color: #666; font-size: 8px; font-family: Consolas;")
            
            stars = QLabel(f"⭐ {s['stars']:,}")
            stars.setStyleSheet("color: #f0ad4e; font-size: 9px;")
            
            layout.addWidget(name)
            layout.addWidget(desc)
            layout.addWidget(cmd)
            layout.addWidget(stars)
            
            widget.setMinimumHeight(80)
            item.setSizeHint(widget.sizeHint())
            self.servers_list.addItem(item)
            self.servers_list.setItemWidget(item, widget)
    
    def populate_skills_list(self):
        self.skills_list.clear()
        for s in self.skills:
            item = QListWidgetItem()
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            name = QLabel(f"☑ {s['name']}")
            name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            
            desc = QLabel(s['description'][:80] + "..." if len(s['description']) > 80 else s['description'])
            desc.setStyleSheet("color: #888; font-size: 9px;")
            
            repo = QLabel(f"📁 {s['repo']}")
            repo.setStyleSheet("color: #666; font-size: 8px; font-family: Consolas;")
            
            stars = QLabel(f"⭐ {s['stars']:,}")
            stars.setStyleSheet("color: #f0ad4e; font-size: 9px;")
            
            layout.addWidget(name)
            layout.addWidget(desc)
            layout.addWidget(repo)
            layout.addWidget(stars)
            
            widget.setMinimumHeight(80)
            item.setSizeHint(widget.sizeHint())
            self.skills_list.addItem(item)
            self.skills_list.setItemWidget(item, widget)
    
    def filter_results(self, text):
        text = text.lower()
        
        # Filter servers
        for i in range(self.servers_list.count()):
            item = self.servers_list.item(i)
            if text:
                item.setHidden(text not in self.servers[i]['name'].lower() and text not in self.servers[i]['description'].lower())
            else:
                item.setHidden(False)
        
        # Filter skills
        for i in range(self.skills_list.count()):
            item = self.skills_list.item(i)
            if text:
                item.setHidden(text not in self.skills[i]['name'].lower() and text not in self.skills[i]['description'].lower())
            else:
                item.setHidden(False)
    
    def sort_results(self, sort_type):
        if sort_type == "Stars (High to Low)":
            self.servers.sort(key=lambda x: x['stars'], reverse=True)
            self.skills.sort(key=lambda x: x['stars'], reverse=True)
        elif sort_type == "Stars (Low to High)":
            self.servers.sort(key=lambda x: x['stars'])
            self.skills.sort(key=lambda x: x['stars'])
        elif sort_type == "Name (A-Z)":
            self.servers.sort(key=lambda x: x['name'].lower())
            self.skills.sort(key=lambda x: x['name'].lower())
        elif sort_type == "Name (Z-A)":
            self.servers.sort(key=lambda x: x['name'].lower(), reverse=True)
            self.skills.sort(key=lambda x: x['name'].lower(), reverse=True)
        
        self.populate_servers_list()
        self.populate_skills_list()
    
    def get_selected_clients(self):
        return [k for k, cb in self.client_checks.items() if cb.isChecked()]
    
    def get_selected_servers(self):
        selected = []
        for i in self.servers_list.selectedIndexes():
            if i.row() < len(self.servers):
                selected.append(self.servers[i.row()])
        return selected
    
    def get_selected_skills(self):
        selected = []
        for i in self.skills_list.selectedIndexes():
            if i.row() < len(self.skills):
                selected.append(self.skills[i.row()])
        return selected


class SkillsManager:
    """Manages downloading and installing skills for various AI clients"""
    
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.temp_dir = None
        self.cloned_repos = {}
    
    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        print(msg)
    
    def get_skills_path(self, client_id):
        """Get the skills folder path for a specific client"""
        client = SUPPORTED_CLIENTS.get(client_id)
        if not client:
            return None
        skills_path = client.get('skills_path')
        if not skills_path:
            return None
        return os.path.expanduser(skills_path)
    
    def clone_repo(self, repo_url):
        """Clone a GitHub repository to temp directory (cached)"""
        if repo_url in self.cloned_repos:
            self.log(f"[*] Using cached repo: {repo_url}")
            return self.cloned_repos[repo_url]
        
        import tempfile
        import urllib.request
        
        self.log(f"[*] Cloning repository: {repo_url}")
        
        temp_dir = tempfile.mkdtemp()
        repo_name = repo_url.split('/')[-1]
        repo_path = os.path.join(temp_dir, repo_name)
        
        git_url = f"https://github.com/{repo_url}.git"
        
        try:
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', git_url, repo_path],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode == 0:
                self.cloned_repos[repo_url] = repo_path
                self.log(f"[+] Successfully cloned {repo_url}")
                return repo_path
            else:
                self.log(f"[!] Failed to clone {repo_url}: {result.stderr}")
                return None
        except Exception as e:
            self.log(f"[!] Error cloning {repo_url}: {e}")
            return None
    
    def install_skill(self, skill_id, client_id):
        """Install a single skill for a specific client"""
        skill = AVAILABLE_SKILLS.get(skill_id)
        if not skill:
            self.log(f"[!] Skill not found: {skill_id}")
            return False
        
        skills_path = self.get_skills_path(client_id)
        if not skills_path:
            self.log(f"[!] Skills not supported for client: {client_id}")
            return False
        
        repo_url = skill['repo']
        folder_name = skill['folder']
        
        repo_path = self.clone_repo(repo_url)
        if not repo_path:
            return False
        
        source_skill_path = os.path.join(repo_path, folder_name)
        if not os.path.exists(source_skill_path):
            self.log(f"[!] Skill folder not found: {source_skill_path}")
            return False
        
        dest_skill_path = os.path.join(skills_path, skill_id)
        
        try:
            os.makedirs(skills_path, exist_ok=True)
            
            if os.path.exists(dest_skill_path):
                self.log(f"[*] Skill already exists at {dest_skill_path}, skipping")
                return True
            
            shutil.copytree(source_skill_path, dest_skill_path)
            self.log(f"[+] Installed {skill['name']} to {skills_path}")
            return True
        except Exception as e:
            self.log(f"[!] Failed to install skill: {e}")
            return False
    
    def install_skills(self, selected_skills, selected_clients):
        """Install multiple skills for multiple clients"""
        results = {}
        
        for client_id in selected_clients:
            client_name = SUPPORTED_CLIENTS.get(client_id, {}).get('name', client_id)
            self.log(f"\n[*] Installing skills for {client_name}...")
            
            skills_path = self.get_skills_path(client_id)
            if not skills_path:
                self.log(f"[!] Skills not supported for {client_name}, skipping")
                continue
            
            client_results = {}
            for skill_id in selected_skills:
                skill_name = AVAILABLE_SKILLS.get(skill_id, {}).get('name', skill_id)
                success = self.install_skill(skill_id, client_id)
                client_results[skill_id] = success
            
            results[client_id] = client_results
        
        return results
    
    def cleanup(self):
        """Clean up temporary cloned repositories"""
        for repo_path in self.cloned_repos.values():
            try:
                if os.path.exists(repo_path):
                    shutil.rmtree(repo_path)
            except Exception as e:
                self.log(f"[!] Error cleaning up {repo_path}: {e}")
        self.cloned_repos = {}


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

        # Split View - 3 Columns
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStretchFactor(0, 35)  # Column 1: 35%
        splitter.setStretchFactor(1, 30)  # Column 2: 30%
        splitter.setStretchFactor(2, 35)  # Column 3: 35%
        
        # COLUMN 1: Servers
        col1_panel = QWidget()
        col1_layout = QVBoxLayout(col1_panel)
        
        grp_srv = QGroupBox("1. MCP Servers")
        grp_srv.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        v_srv = QVBoxLayout()
        
        scroll_srv = QScrollArea()
        scroll_srv.setWidgetResizable(True)
        scroll_srv.setFrameShape(QFrame.Shape.NoFrame)
        
        self.wid_srv = QWidget()
        lay_srv = QVBoxLayout(self.wid_srv)
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
        scroll_srv.setWidget(self.wid_srv)
        v_srv.addWidget(scroll_srv)
        grp_srv.setLayout(v_srv)
        col1_layout.addWidget(grp_srv)
        
        btn_browse_servers = QPushButton("Browse Marketplace")
        btn_browse_servers.setStyleSheet("background-color: #6f42c1; color: white;")
        btn_browse_servers.clicked.connect(lambda: self.show_mcp_market_browser(tab='servers'))
        col1_layout.addWidget(btn_browse_servers)
        
        splitter.addWidget(col1_panel)
        
        # COLUMN 2: Skills
        col2_panel = QWidget()
        col2_layout = QVBoxLayout(col2_panel)
        
        grp_skills = QGroupBox("2. Skills")
        grp_skills.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        v_skills = QVBoxLayout()
        
        scroll_skills = QScrollArea()
        scroll_skills.setWidgetResizable(True)
        scroll_skills.setFrameShape(QFrame.Shape.NoFrame)
        
        wid_skills = QWidget()
        lay_skills = QVBoxLayout(wid_skills)
        lay_skills.setSpacing(8)
        
        self.skill_checkboxes = {}
        
        for k, v in AVAILABLE_SKILLS.items():
            box = QGroupBox()
            box.setStyleSheet("QGroupBox { border: 1px solid #444; border-radius: 5px; margin-top: 5px; }")
            box_l = QVBoxLayout()
            
            cb = QCheckBox(f"{v['name']}")
            cb.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.skill_checkboxes[k] = cb
            
            desc = QLabel(v['description'])
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #AAA; font-size: 9px; margin-left: 20px;")
            
            box_l.addWidget(cb)
            box_l.addWidget(desc)
            box.setLayout(box_l)
            lay_skills.addWidget(box)
        
        lay_skills.addStretch()
        scroll_skills.setWidget(wid_skills)
        v_skills.addWidget(scroll_skills)
        grp_skills.setLayout(v_skills)
        col2_layout.addWidget(grp_skills)
        
        btn_browse_skills = QPushButton("Browse Marketplace")
        btn_browse_skills.setStyleSheet("background-color: #6f42c1; color: white;")
        btn_browse_skills.clicked.connect(lambda: self.show_mcp_market_browser(tab='skills'))
        col2_layout.addWidget(btn_browse_skills)
        
        splitter.addWidget(col2_panel)
        
        # COLUMN 3: Clients + Actions
        col3_panel = QWidget()
        col3_layout = QVBoxLayout(col3_panel)
        
        grp_cli = QGroupBox("3. Target Clients")
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
        col3_layout.addWidget(grp_cli)
        
        btn_browse_clients = QPushButton("Browse Marketplace")
        btn_browse_clients.setStyleSheet("background-color: #6f42c1; color: white;")
        btn_browse_clients.clicked.connect(lambda: self.show_mcp_market_browser(tab='both'))
        col3_layout.addWidget(btn_browse_clients)
        
        # Action Buttons
        btn_preview = QPushButton("Preview Configuration")
        btn_preview.clicked.connect(self.show_preview)
        col3_layout.addWidget(btn_preview)
        
        btn_dry_run = QPushButton("Dry Run")
        btn_dry_run.clicked.connect(self.start_dry_run)
        col3_layout.addWidget(btn_dry_run)
        
        btn_rollback = QPushButton("Rollback (Restore Last Backup)")
        btn_rollback.clicked.connect(self.rollback_config)
        col3_layout.addWidget(btn_rollback)
        
        btn_check = QPushButton("Detect Installed Clients")
        btn_check.clicked.connect(self.detect_installed_clients)
        col3_layout.addWidget(btn_check)
        
        btn_install_deps = QPushButton("Install Missing Dependencies")
        btn_install_deps.clicked.connect(self.install_missing_dependencies)
        col3_layout.addWidget(btn_install_deps)
        
        btn_install_skills = QPushButton("Install Selected Skills")
        btn_install_skills.setStyleSheet("background-color: #28a745; color: white;")
        btn_install_skills.clicked.connect(self.install_skills)
        col3_layout.addWidget(btn_install_skills)
        
        col3_layout.addStretch()
        
        splitter.addWidget(col3_panel)
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
        text_lower = text.lower()
        for k, cb in self.server_checkboxes.items():
            if cb is None:
                continue
            server_name = AVAILABLE_SERVERS[k]['name'].lower()
            server_details = AVAILABLE_SERVERS[k]['details'].lower()
            cb.setVisible(text_lower in server_name or text_lower in server_details)

    def update_status(self, server_id, state):
        if state == Qt.CheckState.Checked:
            self.console.append(f"[Info] Selected: {AVAILABLE_SERVERS[server_id]['name']}")

    def refresh_statuses(self):
        self.log("[*] Checking server statuses...")
        for k in self.server_checkboxes:
            status = self.check_server_status_full(k)
            if k in self.server_status:
                self.server_status[k].setText(f"Status: {status}")
                self.server_status[k].setStyleSheet("color: #2E8B57; font-size: 9px;" if status == "Running" else "color: #B22222; font-size: 9px;")

    def check_server_status_full(self, server_id):
        """Check if a server process is currently running"""
        try:
            if sys.platform == 'win32':
                result = subprocess.run(['tasklist'], capture_output=True, text=True)
                processes = result.stdout.lower()
                server_map = {
                    'semantic-brain': 'node.exe',
                    'memory-server': 'node.exe',
                    'filesystem': 'node.exe',
                    'fetch': 'node.exe',
                    'puppeteer': 'node.exe',
                    'github': 'node.exe',
                    'structural-map': 'uv.exe',
                    'sqlite': 'uv.exe'
                }
                if server_id in server_map:
                    return "Running" if server_map[server_id] in processes else "Stopped"
                return "Unknown"
            else:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                processes = result.stdout.lower()
                if 'npx' in processes or 'uvx' in processes:
                    return "Running"
                return "Stopped"
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
            
            # Create UI elements for custom server
            box = QGroupBox()
            box.setStyleSheet("QGroupBox { border: 1px solid #444; border-radius: 5px; margin-top: 5px; }")
            box_l = QVBoxLayout()
            
            cb = QCheckBox(f"{data['name']}")
            cb.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.server_checkboxes[new_id] = cb
            cb.stateChanged.connect(lambda state, id=new_id: self.update_status(id, state))
            
            req_lbl = QLabel(f"Requires: {data['req']}")
            req_lbl.setStyleSheet("color: #AAA; font-weight: bold; font-size: 10px;")
            
            status_lbl = QLabel("Status: Unknown")
            status_lbl.setStyleSheet("color: #888; font-size: 9px;")
            self.server_status[new_id] = status_lbl
            
            desc = QLabel("<b>Custom Server</b>")
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #CCC; margin-top: 5px;")
            
            box_l.addWidget(cb)
            box_l.addWidget(req_lbl)
            box_l.addWidget(status_lbl)
            box_l.addWidget(desc)
            box.setLayout(box_l)
            
            # Add to the scroll area layout (before the stretch)
            self.wid_srv.layout().insertWidget(self.wid_srv.layout().count() - 1, box)
            
            QMessageBox.information(self, "Success", f"Custom server '{data['name']}' added!")
            self.log(f"[+] Added custom server: {data['name']}")

    def export_settings(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export Settings", "", "JSON Files (*.json)")
        if filename:
            settings = {
                "servers": [k for k, cb in self.server_checkboxes.items() if cb is not None and cb.isChecked()],
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
                    if cb is not None and k in settings.get('servers', []):
                        cb.setChecked(True)
                
                for k, cb in self.client_checkboxes.items():
                    if k in settings.get('clients', []):
                        cb.setChecked(True)
                
                self.log(f"[+] Settings imported from {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import settings: {e}")

    def show_preview(self):
        sel_servers = {k: AVAILABLE_SERVERS[k] for k, cb in self.server_checkboxes.items() if cb is not None and cb.isChecked()}
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
        for k in self.server_checkboxes:
            if self.server_checkboxes[k] is not None:
                status = self.check_server_status_full(k)
                if k in self.server_status:
                    color = "#2E8B57" if status == "Running" else "#B22222"
                    self.server_status[k].setText(f"Status: {status}")
                    self.server_status[k].setStyleSheet(f"color: {color}; font-size: 9px;")

    def install_missing_dependencies(self):
        self.log("[*] Checking for missing dependencies...")
        sel_servers = {k: AVAILABLE_SERVERS[k] for k, cb in self.server_checkboxes.items() if cb is not None and cb.isChecked()}
        reqs = set(s['req'] for s in sel_servers.values())
        
        if not reqs:
            self.log("[*] No servers selected. Checking for all common tools (npm, uv)...")
            reqs = {"npm", "uv"}
        
        missing = []
        for req in reqs:
            if not self.check_tool_availability(req):
                missing.append(req)
        
        if not missing:
            QMessageBox.information(self, "Dependencies", "All required tools are already installed.")
            self.log("[+] All dependencies satisfied.")
            return
        
        missing_str = '\n'.join(f"  - {r}" for r in missing)
        msg = f"The following tools are required but not found in PATH:\n\n{missing_str}\n\nWould you like to attempt automatic installation?"
        reply = QMessageBox.question(self, "Missing Dependencies", msg, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            success = []
            failed = []
            
            for req in missing:
                self.log(f"[*] Installing {req}...")
                install_success = False
                
                if req == "npm":
                    install_success = self.install_npm()
                elif req == "uv":
                    install_success = self.install_uv()
                
                if install_success:
                    success.append(req)
                    self.log(f"[+] {req} installed successfully")
                else:
                    failed.append(req)
                    self.log(f"[!] Failed to install {req}")
            
            if success and not failed:
                QMessageBox.information(self, "Success", f"Successfully installed: {', '.join(success)}")
            elif success and failed:
                QMessageBox.warning(self, "Partial Success", 
                    f"Installed: {', '.join(success)}\nFailed: {', '.join(failed)}")
            else:
                QMessageBox.critical(self, "Installation Failed", 
                    f"Could not install: {', '.join(failed)}\n\nPlease install manually.")

    def install_skills(self):
        sel_clients = [k for k, cb in self.client_checkboxes.items() if cb.isChecked()]
        sel_skills = [k for k, cb in self.skill_checkboxes.items() if cb is not None and cb.isChecked()]
        
        if not sel_clients:
            QMessageBox.warning(self, "No Clients Selected", "Please select at least one target client software.")
            return
        
        if not sel_skills:
            QMessageBox.information(self, "No Skills Selected", "Please select at least one skill to install.")
            return
        
        unsupported = []
        for client_id in sel_clients:
            client = SUPPORTED_CLIENTS.get(client_id, {})
            if not client.get('skills_path'):
                unsupported.append(client.get('name', client_id))
        
        if unsupported:
            msg = f"The following clients do not support skills:\n\n{', '.join(unsupported)}\n\nSkills will only be installed for supported clients."
            reply = QMessageBox.question(self, "Unsupported Clients", msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            sel_clients = [c for c in sel_clients if SUPPORTED_CLIENTS[c].get('skills_path')]
        
        if not sel_clients:
            QMessageBox.information(self, "No Supported Clients", "None of the selected clients support skills installation.")
            return
        
        skill_names = [AVAILABLE_SKILLS[s]['name'] for s in sel_skills]
        client_names = [SUPPORTED_CLIENTS[c]['name'] for c in sel_clients]
        
        msg = f"Install {len(sel_skills)} skill(s) for {len(sel_clients)} client(s)?\n\nSkills: {', '.join(skill_names)}\n\nClients: {', '.join(client_names)}"
        reply = QMessageBox.question(self, "Install Skills", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.log("[*] Starting skills installation...")
        
        skills_manager = SkillsManager(log_callback=self.log)
        
        try:
            results = skills_manager.install_skills(sel_skills, sel_clients)
            
            total_success = 0
            total_failed = 0
            
            for client_id, client_results in results.items():
                client_name = SUPPORTED_CLIENTS.get(client_id, {}).get('name', client_id)
                for skill_id, success in client_results.items():
                    if success:
                        total_success += 1
                    else:
                        total_failed += 1
            
            if total_success > 0 and total_failed == 0:
                QMessageBox.information(self, "Success", 
                    f"Successfully installed {total_success} skill(s)")
            elif total_success > 0 and total_failed > 0:
                QMessageBox.warning(self, "Partial Success",
                    f"Installed: {total_success} skill(s)\nFailed: {total_failed} skill(s)")
            else:
                QMessageBox.critical(self, "Installation Failed",
                    "Could not install any skills. Check the console for details.")
                    
        except Exception as e:
            self.log(f"[!] Error during installation: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")
        finally:
            skills_manager.cleanup()

    def show_mcp_market_browser(self, tab='both'):
        dialog = MCPMarketBrowserDialog(self, default_tab=tab)
        if dialog.exec():
            selected_clients = dialog.get_selected_clients()
            selected_servers = dialog.get_selected_servers()
            selected_skills = dialog.get_selected_skills()
            
            if not selected_clients:
                QMessageBox.warning(self, "No Clients", "Please select at least one target client.")
                return
            
            if not selected_servers and not selected_skills:
                QMessageBox.warning(self, "No Selection", "Please select at least one server or skill to install.")
                return
            
            self.log("[*] Installing from MCP Market...")
            
            # Install servers
            for server in selected_servers:
                self.log(f"    Installing server: {server['name']}")
                for client_id in selected_clients:
                    self.install_mcp_market_server(server, client_id)
            
            # Install skills
            for skill in selected_skills:
                self.log(f"    Installing skill: {skill['name']}")
                for client_id in selected_clients:
                    self.install_mcp_market_skill(skill, client_id)
            
            QMessageBox.information(self, "Success", 
                f"Installed {len(selected_servers)} server(s) and {len(selected_skills)} skill(s)")
    
    def install_mcp_market_server(self, server, client_id):
        """Install a server from MCP Market to a client"""
        try:
            client = SUPPORTED_CLIENTS.get(client_id)
            if not client:
                return False
            
            # Parse the command to get package name
            cmd = server.get('command', '')
            if not cmd:
                return False
            
            # Get config path
            config_paths = client.get('paths', [])
            config_path = None
            for p in config_paths:
                expanded = os.path.expanduser(p.replace("~", os.path.expanduser("~")))
                if os.path.exists(os.path.dirname(expanded)):
                    config_path = expanded
                    break
            
            if not config_path:
                return False
            
            # Read existing config
            config = {}
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            
            if 'mcpServers' not in config:
                config['mcpServers'] = {}
            
            # Add server
            server_name = server['name'].lower().replace(' ', '-')
            config['mcpServers'][server_name] = {
                "command": cmd,
                "args": server.get('args', []),
                "env": {}
            }
            
            # Write config
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.log(f"    [+] Added {server['name']} to {client['name']}")
            return True
        except Exception as e:
            self.log(f"    [!] Failed to install {server['name']}: {e}")
            return False
    
    def install_mcp_market_skill(self, skill, client_id):
        """Install a skill from MCP Market to a client"""
        try:
            client = SUPPORTED_CLIENTS.get(client_id)
            if not client or not client.get('skills_path'):
                return False
            
            skills_path = os.path.expanduser(client['skills_path'])
            os.makedirs(skills_path, exist_ok=True)
            
            skill_name = skill['name'].lower().replace(' ', '-')
            skill_dest = os.path.join(skills_path, skill_name)
            
            if os.path.exists(skill_dest):
                self.log(f"    [*] Skill {skill['name']} already exists")
                return True
            
            # Clone the repo
            repo = skill.get('repo', '')
            if not repo:
                return False
            
            self.log(f"    [*] Cloning skill from {repo}...")
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', f'https://github.com/{repo}.git', skill_dest],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.log(f"    [+] Added skill {skill['name']} to {client['name']}")
                return True
            else:
                self.log(f"    [!] Failed to clone skill: {result.stderr}")
                return False
        except Exception as e:
            self.log(f"    [!] Failed to install skill {skill['name']}: {e}")
            return False

    def rollback_config(self):
        backups = []
        user_home = os.path.expanduser("~")
        
        for k, client_data in SUPPORTED_CLIENTS.items():
            for path in client_data['paths']:
                expanded = path.replace("~", user_home)
                config_basename = os.path.basename(expanded)
                parent_dir = os.path.dirname(expanded)
                if not os.path.exists(parent_dir):
                    continue
                matching = [f for f in os.listdir(parent_dir) 
                           if f.startswith(config_basename + '.') and f.endswith('.bak')]
                if matching:
                    backups.extend([os.path.join(parent_dir, f) for f in matching])
        
        if not backups:
            QMessageBox.information(self, "Rollback", "No backup files found.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Backup to Restore")
        layout = QVBoxLayout(dialog)
        
        list_widget = QListWidget()
        for b in sorted(backups):
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

    def run_elevated(self, command, description):
        self.log(f"[*] Attempting elevated install: {description}")
        self.log("[*] UAC prompt should appear...")
        try:
            if sys.platform == 'win32':
                subprocess.Popen(
                    ['powershell', '-Command', f'Start-Process', 'cmd.exe', '-ArgumentList', f'/c {command}', '-Verb', 'RunAs', '-Wait'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                return True
            else:
                return False
        except Exception as e:
            self.log(f"[!] Elevation failed: {e}")
            return False

    def install_npm(self):
        self.log("[*] Installing Node.js (npm)...")
        
        if not sys.platform == 'win32':
            self.log("[!] Automatic npm/Node.js installation is only supported on Windows.")
            return False
        
        try:
            import urllib.request
            import tempfile
        except ImportError:
            self.log("[!] urllib not available")
            return False
        
        temp_dir = tempfile.gettempdir()
        msi_path = os.path.join(temp_dir, "node-installer.msi")
        url = "https://nodejs.org/dist/v22.12.0/node-v22.12.0-x64.msi"
        
        try:
            self.log(f"    Downloading Node.js from {url}...")
            urllib.request.urlretrieve(url, msi_path)
            self.log(f"    Downloaded to {msi_path}")
        except Exception as e:
            self.log(f"[!] Download failed: {e}")
            self.log(f"    Manual install: https://nodejs.org/")
            return False
        
        self.log("    Running installer (attempt 1 - without elevation)...")
        try:
            result = subprocess.run(
                ['msiexec', '/i', msi_path, '/quiet', '/norestart'],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0 or result.returncode == 3010:
                self.log("    [+] Node.js installed successfully!")
                try:
                    if os.path.exists(msi_path):
                        os.remove(msi_path)
                except:
                    pass
                return True
        except Exception as e:
            self.log(f"    [!] Install attempt 1 failed: {e}")
        
        self.log("    Running installer (attempt 2 - with elevation)...")
        if self.run_elevated(f'msiexec /i "{msi_path}" /quiet /norestart', "Node.js"):
            self.log("    [+] Node.js installed successfully (elevated)!")
            try:
                if os.path.exists(msi_path):
                    os.remove(msi_path)
            except:
                pass
            return True
        
        try:
            if os.path.exists(msi_path):
                os.remove(msi_path)
        except:
            pass
        
        self.log("[!] Node.js installation failed.")
        self.log(f"    Please install manually from: https://nodejs.org/")
        return False

    def install_uv(self):
        self.log("[*] Installing uv...")
        python_exe = sys.executable
        
        self.log("    Attempt 1: pip install uv")
        try:
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "uv"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                self.log("    [+] uv installed via pip!")
                return True
            self.log(f"    pip install failed: {result.stderr}")
        except Exception as e:
            self.log(f"    [!] pip install failed: {e}")
        
        self.log("    Attempt 2: pip install uv (with elevation)")
        if self.run_elevated(f'"{python_exe}" -m pip install uv', "uv via pip"):
            try:
                result = subprocess.run(
                    [python_exe, "-m", "pip", "show", "uv"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.log("    [+] uv installed via pip (elevated)!")
                    return True
            except Exception:
                pass
        
        self.log("    Attempt 3: curl install script")
        try:
            curl_cmd = 'powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"'
            result = subprocess.run(
                curl_cmd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=120
            )
            if result.returncode == 0:
                self.log("    [+] uv installed via curl script!")
                return True
            self.log(f"    curl install failed: {result.stderr}")
        except Exception as e:
            self.log(f"    [!] curl install failed: {e}")
        
        self.log("    Attempt 4: curl install (with elevation)")
        if self.run_elevated('powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"', "uv via curl"):
            try:
                result = subprocess.run(
                    [python_exe, "-m", "pip", "show", "uv"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.log("    [+] uv installed via curl (elevated)!")
                    return True
            except Exception:
                pass
        
        self.log("[!] uv installation failed.")
        self.log(f"    Please install manually from: https://github.com/astral-sh/uv")
        return False

    def get_secure_input(self, title, label):
        text, ok = QInputDialog.getText(self, title, label, QLineEdit.EchoMode.Password)
        return text.strip() if ok else None

    def start_process(self, dry_run=False):
        self.console.clear()
        
        sel_servers = {k: AVAILABLE_SERVERS[k] for k, cb in self.server_checkboxes.items() if cb is not None and cb.isChecked()}
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

        for k, s in list(sel_servers.items()):
            if s.get("secure_prompt"):
                token = self.get_secure_input(f"Setup {s['name']}", f"Enter API Token for {s['name']}:")
                if not token:
                    self.log(f"[!] Skipped {s['name']} (No token provided by user)")
                    del sel_servers[k]
                else:
                    s_config = copy.deepcopy(s["config"])
                    s_config["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] = token
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
        if server_id in self.server_status and self.server_status[server_id]:
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
