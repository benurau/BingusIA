import asyncio
import io
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from enum import Enum
from pathlib import Path

from bingus_ia.core.agent import Agent
from bingus_ia.core.config import load_config, save_config
from bingus_ia.core.types import AgentConfig


# ── Windows Terminal classic colors ───────────────────────────────
TERM_BG = "#000000"
TERM_FG = "#c0c0c0"
TERM_BOLD = "#ffffff"
TERM_PROMPT = "#569CD6"
TERM_AGENT = "#6A9955"
TERM_ERROR = "#F44747"
TERM_INFO = "#969696"
TERM_SEP = "#333333"
TERM_INPUT_BG = "#000000"
TERM_ACCENT = "#007acc"

# ── Editor / Explorer colors ──────────────────────────────────────
EDITOR_BG = "#1e1e1e"
EDITOR_FG = "#d4d4d4"
HEADER_BG = "#252526"
EXPLORER_BG = "#252526"
SEL_BG = "#264f78"
SCROLL_BG = "#1e1e1e"
SCROLL_FG = "#424242"
SCROLL_THUMB = "#424242"
SCROLL_THUMB_ACTIVE = "#555555"


class AutoHideScrollbar(tk.Scrollbar):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=SCROLL_BG, troughcolor=SCROLL_BG,
                         activebackground=SCROLL_THUMB_ACTIVE, elementborderwidth=0,
                         width=10, **kwargs)

    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.pack_forget()
        else:
            try:
                self.pack(side=tk.RIGHT, fill=tk.Y)
            except tk.TclError:
                pass
        super().set(lo, hi)

# ── Syntax highlight colors ───────────────────────────────────────
SYNTAX_KEYWORD = "#569CD6"
SYNTAX_STRING = "#CE9178"
SYNTAX_COMMENT = "#6A9955"
SYNTAX_NUMBER = "#B5CEA8"
SYNTAX_BUILTIN = "#DCDCAA"
SYNTAX_DECORATOR = "#C586C0"
SYNTAX_FUNC = "#DCDCAA"


class SetupState(Enum):
    PROVIDER = 0
    OLLAMA_URL = 1
    OLLAMA_MODEL = 2
    API_KEY = 3
    API_BASE_URL = 4
    MODEL_NAME = 5
    DONE = 6


PROVIDER_NAMES = ["ollama", "openai", "anthropic", "opencode"]

PY_KEYWORDS = (
    "False|None|True|and|as|assert|async|await|break|class|continue|def|del|"
    "elif|else|except|finally|for|from|global|if|import|in|is|lambda|"
    "nonlocal|not|or|pass|raise|return|try|while|with|yield"
)

PY_BUILTINS = (
    "print|len|range|int|str|float|list|dict|tuple|set|bool|type|"
    "isinstance|hasattr|getattr|setattr|delattr|open|file|input|"
    "super|object|property|staticmethod|classmethod|"
    "enumerate|zip|map|filter|sorted|reversed|"
    "min|max|sum|abs|round|any|all|repr|"
    "Exception|ValueError|TypeError|KeyError|IndexError|AttributeError|"
    "RuntimeError|OSError|ImportError|NameError|SyntaxError|"
    "BaseException|SystemExit|KeyboardInterrupt"
)

HIGHLIGHT_RULES: list[tuple[str, str, str]] = [
    (r"#[^\n]*", SYNTAX_COMMENT, "comment"),
    (r"\"\"\"[\s\S]*?\"\"\"", SYNTAX_STRING, "docstring"),
    (r"'''.*?'''", SYNTAX_STRING, "docstring"),
    (r"\"[^\"\n]*\"", SYNTAX_STRING, "string"),
    (r"'[^'\n]*'", SYNTAX_STRING, "string"),
    (r"f\"[^\"\n]*\"", SYNTAX_STRING, "fstring"),
    (r"f'[^'\n]*'", SYNTAX_STRING, "fstring"),
    (r"\b\d+\.?\d*\b", SYNTAX_NUMBER, "number"),
    (r"\b(" + PY_KEYWORDS + r")\b", SYNTAX_KEYWORD, "keyword"),
    (r"\b(" + PY_BUILTINS + r")\b", SYNTAX_BUILTIN, "builtin"),
    (r"@\w+", SYNTAX_DECORATOR, "decorator"),
]

HIGHLIGHT_TAGS = {
    "keyword": SYNTAX_KEYWORD,
    "builtin": SYNTAX_BUILTIN,
    "string": SYNTAX_STRING,
    "comment": SYNTAX_COMMENT,
    "number": SYNTAX_NUMBER,
    "decorator": SYNTAX_DECORATOR,
    "docstring": SYNTAX_STRING,
    "fstring": SYNTAX_STRING,
    "func": SYNTAX_FUNC,
}


def _run_ollama_fetch(url: str) -> list[str]:
    import httpx
    try:
        resp = httpx.get(f"{url.rstrip('/')}/api/tags", timeout=10)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            names = [m.get("name", m.get("model", "")) for m in models]
            return [n for n in names if n]
    except Exception:
        pass
    return []


def _highlight_python(text: str) -> list[tuple[str, str]]:
    spans: list[tuple[int, int, str]] = []
    for pattern, color, tag in HIGHLIGHT_RULES:
        for m in re.finditer(pattern, text):
            spans.append((m.start(), m.end(), tag))
    spans.sort(key=lambda x: (x[0], -x[1]))

    merged: list[tuple[int, int, str]] = []
    for start, end, tag in spans:
        if merged and start < merged[-1][1]:
            continue
        merged.append((start, end, tag))

    result: list[tuple[str, str]] = []
    pos = 0
    for start, end, tag in merged:
        if start > pos:
            result.append((text[pos:start], ""))
        result.append((text[start:end], tag))
        pos = end
    if pos < len(text):
        result.append((text[pos:], ""))
    return result


# ── AgentRunner ────────────────────────────────────────────────────
class AgentRunner:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent: Agent | None = None
        self.input_queue: queue.Queue = queue.Queue()
        self.output_queue: queue.Queue = queue.Queue()
        self._running = True
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._wait_for_agent()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        sys.stdout = stdout_buf
        sys.stderr = stderr_buf
        try:
            self.agent = Agent(self.config)
            self.output_queue.put(("ready", ""))
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.output_queue.put(("error", f"Agent init failed: {e}"))
            return
        while self._running:
            try:
                prompt = self.input_queue.get(timeout=0.2)
                if prompt is None:
                    break
                result = self._loop.run_until_complete(self.agent.run(prompt))
                out_output = self._strip_ansi(stdout_buf.getvalue())
                stdout_buf.truncate(0)
                stdout_buf.seek(0)
                err_output = stderr_buf.getvalue()
                stderr_buf.truncate(0)
                stderr_buf.seek(0)
                if out_output.strip():
                    self.output_queue.put(("stdout", out_output.strip()))
                if err_output.strip():
                    self.output_queue.put(("stderr", err_output.strip()))
                self.output_queue.put(("response", result))
            except queue.Empty:
                continue
            except Exception as e:
                out_output = self._strip_ansi(stdout_buf.getvalue())
                stdout_buf.truncate(0)
                stdout_buf.seek(0)
                err_output = stderr_buf.getvalue()
                stderr_buf.truncate(0)
                stderr_buf.seek(0)
                if out_output.strip():
                    self.output_queue.put(("stdout", out_output.strip()))
                if err_output.strip():
                    self.output_queue.put(("stderr", err_output.strip()))
                self.output_queue.put(("error", str(e)))
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        self._loop.run_until_complete(self.agent.close())
        self._loop.close()

    @staticmethod
    def _strip_ansi(text: str) -> str:
        return re.sub(r'\033\[[0-9;]*m', '', text)

    def _wait_for_agent(self, timeout: float = 15.0):
        start = time.time()
        while time.time() - start < timeout:
            try:
                msg = self.output_queue.get(timeout=0.5)
                if msg[0] == "ready":
                    return
                if msg[0] == "error":
                    raise RuntimeError(msg[1])
            except queue.Empty:
                continue
        raise TimeoutError("Agent failed to initialize")

    def submit(self, prompt: str):
        self.input_queue.put(prompt)

    def poll(self) -> tuple[str, str] | None:
        try:
            return self.output_queue.get_nowait()
        except queue.Empty:
            return None

    def set_current_file(self, path: str | None, content: str = ""):
        if self.agent:
            self._loop.call_soon_threadsafe(
                self.agent.set_current_file, path, content
            )

    def stop(self):
        self._running = False
        self.input_queue.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout=5)


# ── TerminalPanel ─────────────────────────────────────────────────
class TerminalPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, on_submit=None):
        super().__init__(parent, bg=TERM_BG)
        self.on_submit = on_submit
        self._history: list[str] = []
        self._history_index = -1
        self._build_ui()

    def _build_ui(self):
        self.output_area = tk.Text(self, wrap=tk.WORD, font=("Consolas", 10),
                                   bg=TERM_BG, fg=TERM_FG, insertbackground=TERM_FG,
                                   state=tk.DISABLED, relief=tk.FLAT,
                                   selectbackground=SEL_BG, padx=6, pady=4,
                                   highlightthickness=0, borderwidth=0)
        self.output_area.pack(fill=tk.BOTH, expand=True)
        scroll = AutoHideScrollbar(self.output_area, orient=tk.VERTICAL)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_area.config(yscrollcommand=scroll.set)
        scroll.config(command=self.output_area.yview)

        input_frame = tk.Frame(self, bg=TERM_BG)
        input_frame.pack(fill=tk.X)

        prompt_lbl = tk.Label(input_frame, text=">", font=("Consolas", 10),
                              bg=TERM_BG, fg=TERM_FG, width=1)
        prompt_lbl.pack(side=tk.LEFT)

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(input_frame, textvariable=self.input_var,
                                    font=("Consolas", 10), bg=TERM_BG, fg=TERM_FG,
                                    insertbackground=TERM_FG, relief=tk.FLAT,
                                    highlightthickness=0, bd=0)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.input_entry.bind("<Return>", self._on_submit)
        self.input_entry.bind("<Up>", self._history_up)
        self.input_entry.bind("<Down>", self._history_down)
        self.input_entry.bind("<Control-z>", self._undo_input)
        self.input_entry.bind("<Control-Z>", self._undo_input)

        self.output_area.tag_config("user", foreground=TERM_PROMPT)
        self.output_area.tag_config("agent", foreground=TERM_AGENT)
        self.output_area.tag_config("error", foreground=TERM_ERROR)
        self.output_area.tag_config("info", foreground=TERM_INFO)
        self.output_area.tag_config("prompt", foreground=TERM_BOLD)
        self.output_area.tag_config("sep", foreground=TERM_SEP)
        self.output_area.tag_config("bold", font=("Consolas", 10, "bold"))
        self.input_entry.focus_set()

    def _on_submit(self, event=None):
        text = self.input_var.get()
        self.input_var.set("")
        if text:
            self._history.append(text)
        self._history_index = len(self._history)
        if self.on_submit:
            self.on_submit(text)

    def _history_up(self, event=None):
        if not self._history:
            return
        self._history_index = max(0, self._history_index - 1)
        self.input_var.set(self._history[self._history_index])

    def _history_down(self, event=None):
        if self._history_index >= len(self._history):
            return
        self._history_index += 1
        if self._history_index >= len(self._history):
            self.input_var.set("")
            self._history_index = len(self._history)
        else:
            self.input_var.set(self._history[self._history_index])

    def _undo_input(self, event=None):
        current = self.input_var.get()
        if current:
            self.input_var.set("")
        return "break"

    def write(self, text: str, tag: str = ""):
        self.output_area.config(state=tk.NORMAL)
        self.output_area.insert(tk.END, text, tag)
        self.output_area.see(tk.END)
        self.output_area.config(state=tk.DISABLED)

    def writeline(self, text: str, tag: str = ""):
        self.write(text + "\n", tag)

    def set_waiting(self, waiting: bool):
        state = tk.NORMAL if not waiting else tk.DISABLED
        self.input_entry.config(state=state)

    def focus_input(self):
        self.input_entry.focus_set()


# ── SyntaxHighlightText ───────────────────────────────────────────
class SyntaxHighlightText(tk.Text):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._highlight_after = None

        for tag, color in HIGHLIGHT_TAGS.items():
            self.tag_config(tag, foreground=color)

        self.bind("<<Modified>>", self._on_modified)

    def _on_modified(self, event=None):
        if self.edit_modified():
            self.edit_modified(False)
            if self._highlight_after:
                self.after_cancel(self._highlight_after)
            self._highlight_after = self.after(400, self._rehighlight)

    def _rehighlight(self):
        for tag in HIGHLIGHT_TAGS:
            self.tag_remove(tag, "1.0", tk.END)
        try:
            text = self.get("1.0", tk.END)
        except tk.TclError:
            return
        char_pos = 0
        for segment, tag in _highlight_python(text):
            if tag and segment:
                line = text[:char_pos].count("\n") + 1
                col = char_pos - text[:char_pos].rfind("\n") - 1
                start = f"{line}.{col}"
                try:
                    self.tag_add(tag, start, f"{start}+{len(segment)}c")
                except tk.TclError:
                    pass
            char_pos += len(segment)

    def load_content(self, content: str):
        self.delete("1.0", tk.END)
        self.insert("1.0", content)
        self.edit_reset()
        self.edit_modified(False)
        self.after(200, self._rehighlight)


# ── EditorPanel ───────────────────────────────────────────────────
class EditorPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, on_file_open=None):
        super().__init__(parent, bg=HEADER_BG)
        self._filepath: str | None = None
        self._mtime: float = 0.0
        self._modified = False
        self.on_file_open = on_file_open
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg=HEADER_BG)
        header.pack(fill=tk.X)

        self.file_label = tk.Label(header, text="EDITOR (no file open)",
                                   font=("Segoe UI", 9, "bold"),
                                   bg=HEADER_BG, fg=TERM_INFO, anchor="w", padx=8, pady=4)
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_font = ("Segoe UI", 8)
        btn_frame = tk.Frame(header, bg=HEADER_BG)
        btn_frame.pack(side=tk.RIGHT, padx=4)

        self.open_btn = tk.Button(btn_frame, text="Open", command=self._open_file,
                                  font=btn_font, bg=HEADER_BG, fg=TERM_FG,
                                  activebackground="#333", activeforeground=TERM_FG,
                                  relief=tk.FLAT, padx=6, pady=1, cursor="hand2")
        self.open_btn.pack(side=tk.LEFT, padx=1)
        self.save_btn = tk.Button(btn_frame, text="Save", command=self._save_file,
                                  font=btn_font, bg=HEADER_BG, fg=TERM_FG,
                                  activebackground="#333", activeforeground=TERM_FG,
                                  relief=tk.FLAT, padx=6, pady=1, cursor="hand2",
                                  state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=1)
        self.reload_btn = tk.Button(btn_frame, text="Reload", command=self._reload_file,
                                    font=btn_font, bg=HEADER_BG, fg=TERM_FG,
                                    activebackground="#333", activeforeground=TERM_FG,
                                    relief=tk.FLAT, padx=6, pady=1, cursor="hand2",
                                    state=tk.DISABLED)
        self.reload_btn.pack(side=tk.LEFT, padx=1)

        editor_frame = tk.Frame(self, bg=EDITOR_BG)
        editor_frame.pack(fill=tk.BOTH, expand=True)

        self.editor = SyntaxHighlightText(
            editor_frame, wrap=tk.WORD, font=("Consolas", 10),
            bg=EDITOR_BG, fg=EDITOR_FG, insertbackground=EDITOR_FG,
            relief=tk.FLAT, selectbackground=SEL_BG,
            padx=8, pady=4, undo=True, highlightthickness=0, borderwidth=0,
        )
        self.editor.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll = AutoHideScrollbar(editor_frame, orient=tk.VERTICAL)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor.config(yscrollcommand=scroll.set)
        scroll.config(command=self.editor.yview)

    def _open_file(self, path: str | None = None):
        if path is None:
            path = filedialog.askopenfilename(
                title="Open File",
                filetypes=[("All Files", "*.*"), ("Python", "*.py"),
                           ("Text", "*.txt"), ("Markdown", "*.md")])
        if not path:
            return
        self._filepath = path
        content = self._load_file_content()
        if content is None:
            return
        try:
            self._mtime = os.path.getmtime(path)
        except OSError:
            self._mtime = 0.0
        self._modified = False
        self.file_label.config(text=f"EDITOR: {Path(path).name}")
        self.save_btn.config(state=tk.NORMAL)
        self.reload_btn.config(state=tk.NORMAL)
        if self.on_file_open:
            self.on_file_open(path, content)

    def _load_file_content(self) -> str | None:
        try:
            with open(self._filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return None
        self.editor.load_content(content)
        return content

    def _save_file(self, event=None):
        if not self._filepath:
            return
        content = self.editor.get("1.0", tk.END).rstrip("\n")
        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                f.write(content + "\n" if content else "")
            self._mtime = os.path.getmtime(self._filepath)
            self._modified = False
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    def _reload_file(self, event=None):
        if not self._filepath:
            return
        if self._modified and not messagebox.askyesno("Unsaved Changes",
                                                      "Reload will lose unsaved changes. Continue?"):
            return
        self._load_file_content()
        try:
            self._mtime = os.path.getmtime(self._filepath)
        except OSError:
            self._mtime = 0.0
        self._modified = False

    def check_external_change(self):
        if not self._filepath or not os.path.exists(self._filepath):
            return
        try:
            current = os.path.getmtime(self._filepath)
        except OSError:
            return
        if current != self._mtime:
            self._mtime = current
            if self._modified:
                self.file_label.config(text=f"EDITOR: {Path(self._filepath).name} [ext]")
            else:
                self._load_file_content()


# ── FileExplorer ──────────────────────────────────────────────────
class FileExplorer(tk.Frame):
    def __init__(self, parent: tk.Widget, editor: EditorPanel, on_folder_open=None):
        super().__init__(parent, bg=EXPLORER_BG)
        self.editor = editor
        self.on_folder_open = on_folder_open
        self._root_path: str | None = None
        self._build_ui()

    def _build_ui(self):
        header = tk.Label(self, text="EXPLORER", font=("Segoe UI", 9, "bold"),
                          bg=HEADER_BG, fg=TERM_INFO, anchor="w", padx=8, pady=4)
        header.pack(fill=tk.X)

        btn_frame = tk.Frame(self, bg=HEADER_BG)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="Open Folder", command=self.open_folder,
                  font=("Segoe UI", 8), bg=HEADER_BG, fg=TERM_FG,
                  activebackground="#333", activeforeground=TERM_FG,
                  relief=tk.FLAT, padx=6, pady=1, cursor="hand2").pack(side=tk.LEFT, padx=4, pady=2)
        tk.Button(btn_frame, text="Refresh", command=self._refresh_tree,
                  font=("Segoe UI", 8), bg=HEADER_BG, fg=TERM_FG,
                  activebackground="#333", activeforeground=TERM_FG,
                  relief=tk.FLAT, padx=6, pady=1, cursor="hand2").pack(side=tk.LEFT, padx=2, pady=2)

        tree_frame = tk.Frame(self, bg=EXPLORER_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=EXPLORER_BG, foreground=TERM_FG,
                        fieldbackground=EXPLORER_BG, font=("Consolas", 9), rowheight=22)
        style.map("Treeview", background=[("selected", SEL_BG)],
                  foreground=[("selected", TERM_FG)])
        style.configure("Treeview.Heading", background=HEADER_BG, foreground=TERM_FG,
                        font=("Segoe UI", 8), relief=tk.FLAT)

        self.tree = ttk.Treeview(tree_frame, show="tree", columns=(), style="Treeview")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = AutoHideScrollbar(tree_frame, orient=tk.VERTICAL)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scroll.set)
        scroll.config(command=self.tree.yview)
        self.tree.bind("<Double-1>", self._on_item_double_click)

    def open_folder(self, path: str | None = None):
        if path is None:
            path = filedialog.askdirectory(title="Open Folder")
        if not path:
            return
        self._root_path = path
        self._refresh_tree()
        if self.on_folder_open:
            self.on_folder_open(path)

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        if self._root_path:
            self._populate_tree("", self._root_path)

    def _populate_tree(self, parent_id: str, dirpath: str):
        try:
            items = sorted(os.listdir(dirpath))
        except PermissionError:
            return
        dirs = [n for n in items if os.path.isdir(os.path.join(dirpath, n))]
        files = [n for n in items if os.path.isfile(os.path.join(dirpath, n))]
        for name in dirs + files:
            full = os.path.join(dirpath, name)
            is_dir = os.path.isdir(full)
            node = self.tree.insert(parent_id, tk.END, text=name, open=False)
            self.tree.item(node, values=(full,))
            if is_dir:
                self._populate_tree(node, full)

    def _on_item_double_click(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        full = self.tree.item(sel[0], "values")
        if full and os.path.isfile(full[0]):
            self.editor._open_file(full[0])


# ── BingusGUI ─────────────────────────────────────────────────────
class BingusGUI(tk.Tk):
    def __init__(self, config: AgentConfig | None = None):
        super().__init__()
        self.title("Bingus IA — AI Programming Assistant")
        self.geometry("1500x850")
        self.minsize(1000, 500)
        self.configure(bg=HEADER_BG)

        self.config: AgentConfig | None = None
        self.agent_runner: AgentRunner | None = None
        self._setup_state = SetupState.PROVIDER
        self._ollama_models: list[str] = []
        self._poller_running = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if config and config.provider:
            self.config = config
            self._finish_setup()
        else:
            self._start_setup()

    def _build_ui(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=HEADER_BG,
                               sashrelief=tk.FLAT, sashwidth=3)
        paned.pack(fill=tk.BOTH, expand=True)

        self.terminal = TerminalPanel(paned, on_submit=self._on_input)
        paned.add(self.terminal, stretch="always", width=500)

        self.editor = EditorPanel(paned, on_file_open=self._on_file_open)
        paned.add(self.editor, stretch="always", width=550)

        self.explorer = FileExplorer(paned, self.editor,
                                     on_folder_open=self._on_folder_open)
        paned.add(self.explorer, stretch="never", width=220)

    def _print_banner(self):
        self.terminal.writeline("Bingus IA \u2014 Agentic Programming Assistant", "bold")
        self.terminal.writeline("\u2500" * 50, "sep")

    # ── Setup flow ────────────────────────────────────────────────
    def _start_setup(self):
        self._print_banner()
        self._setup_state = SetupState.PROVIDER
        self._show_providers()

    def _show_providers(self):
        self.terminal.writeline("Available providers:", "info")
        for i, p in enumerate(PROVIDER_NAMES, 1):
            self.terminal.writeline(f"  [{i}] {p}", "prompt")
        self.terminal.write("Select provider [1-4] (Enter for ollama): ", "prompt")
        self.terminal.focus_input()

    def _show_ollama_url(self):
        self.terminal.write("Ollama URL (Enter for http://localhost:11434): ", "prompt")
        self.terminal.focus_input()

    def _show_ollama_models(self):
        if not self._ollama_models:
            self.terminal.writeline("  No models found or could not reach Ollama.", "error")
            self.config.model = "codellama:7b"
            self._finish_setup()
            return
        self.terminal.writeline("Available models:", "info")
        default_model = self.config.model or self._ollama_models[0]
        for i, name in enumerate(self._ollama_models, 1):
            marker = " (default)" if name == default_model else ""
            self.terminal.writeline(f"  [{i}] {name}{marker}", "prompt")
        self.terminal.write(f"Select model [1-{len(self._ollama_models)}] (Enter for {default_model}): ", "prompt")
        self.terminal.focus_input()

    def _show_api_key(self):
        self.terminal.write(f"API key for {self.config.provider}: ", "prompt")
        self.terminal.focus_input()

    def _show_api_base_url(self):
        defaults = {"openai": "https://api.openai.com/v1",
                    "anthropic": "https://api.anthropic.com/v1",
                    "opencode": "https://opencode.ai/zen/v1"}
        dflt = defaults.get(self.config.provider, "")
        self.terminal.write(f"API base URL (Enter for {dflt}): ", "prompt")
        self.terminal.focus_input()

    def _show_model_name(self):
        dflt = self.config.model or "gpt-4o"
        if self.config.provider == "opencode":
            dflt = "big-pickle"
        self.terminal.write(f"Model name (Enter for {dflt}): ", "prompt")
        self.terminal.focus_input()

    def _on_input(self, text: str):
        if self._setup_state != SetupState.DONE:
            if text:
                self.terminal.writeline(f">>> {text}", "user")
            else:
                self.terminal.writeline(">>> (default)", "prompt")
            self._handle_setup_input(text)
        elif self.agent_runner:
            if text:
                self.terminal.writeline(f">>> {text}", "user")
            self.terminal.set_waiting(True)
            self.agent_runner.submit(text)
            self.after(100, self._poll_agent)
        else:
            self.terminal.writeline("Agent not ready. Restart the application.", "error")

    def _handle_setup_input(self, text: str):
        state = self._setup_state

        if state == SetupState.PROVIDER:
            if not text:
                idx = 0
            else:
                try:
                    idx = int(text) - 1
                except ValueError:
                    idx = -1
            if idx < 0 or idx >= len(PROVIDER_NAMES):
                self.terminal.writeline(f"Enter a number between 1 and {len(PROVIDER_NAMES)}", "error")
                self._show_providers()
                return
            provider = PROVIDER_NAMES[idx]
            if self.config is None:
                self.config = AgentConfig()
            self.config.provider = provider
            self.config.model = "codellama:7b"

            if provider == "ollama":
                self._setup_state = SetupState.OLLAMA_URL
                self._show_ollama_url()
            else:
                self._setup_state = SetupState.API_KEY
                self._show_api_key()

        elif state == SetupState.OLLAMA_URL:
            if text:
                self.config.ollama_base_url = text
            else:
                self.terminal.writeline(f"  Using default: {self.config.ollama_base_url}", "info")
            self.terminal.writeline(f"  Fetching models...", "info")
            self.terminal.set_waiting(True)
            threading.Thread(target=self._fetch_and_show_ollama_models, daemon=True).start()

        elif state == SetupState.OLLAMA_MODEL:
            if not text:
                pass
            elif text.isdigit():
                idx = int(text) - 1
                if 0 <= idx < len(self._ollama_models):
                    self.config.model = self._ollama_models[idx]
            else:
                self.config.model = text
            self._finish_setup()

        elif state == SetupState.API_KEY:
            if text:
                self.config.api_key = text
            self._setup_state = SetupState.API_BASE_URL
            self._show_api_base_url()

        elif state == SetupState.API_BASE_URL:
            if text:
                self.config.api_base_url = text
            self._setup_state = SetupState.MODEL_NAME
            self._show_model_name()

        elif state == SetupState.MODEL_NAME:
            defaults = {"opencode": "big-pickle", "ollama": "codellama:7b",
                        "openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514"}
            if text:
                self.config.model = text
            else:
                self.config.model = defaults.get(self.config.provider, self.config.model)
            self._finish_setup()

    def _fetch_and_show_ollama_models(self):
        models = _run_ollama_fetch(self.config.ollama_base_url)
        self.after(0, self._on_ollama_models_fetched, models)

    def _on_ollama_models_fetched(self, models: list[str]):
        self.terminal.set_waiting(False)
        self._ollama_models = models
        if models:
            self.config.model = models[0] if self.config.model not in models else self.config.model
        self._setup_state = SetupState.OLLAMA_MODEL
        self._show_ollama_models()

    def _finish_setup(self):
        save_config(self.config)
        self.terminal.writeline("\u2500" * 50, "sep")
        line = f"  Provider: {self.config.provider}  |  Model: {self.config.model}"
        if self.config.provider == "ollama":
            line += f"  |  Ollama: {self.config.ollama_base_url}"
        else:
            line += f"  |  API Key: {'<set>' if self.config.api_key else '<not set>'}"
        self.terminal.writeline(line, "info")
        self.terminal.writeline("Starting agent...", "info")
        self.terminal.writeline("\u2500" * 50, "sep")
        self.terminal.set_waiting(True)
        threading.Thread(target=self._init_agent_thread, daemon=True).start()

    def _init_agent_thread(self):
        try:
            self.agent_runner = AgentRunner(self.config)
            self.after(0, self._on_agent_ready)
        except Exception as e:
            self.after(0, self._on_agent_error, str(e))

    def _on_agent_ready(self):
        self._setup_state = SetupState.DONE
        self.terminal.set_waiting(False)
        if self.config and self.config.workspace_dir:
            ws = self.config.workspace_dir
            if os.path.isdir(ws):
                self.explorer.open_folder(ws)
        self.terminal.writeline("Agent ready. Enter your prompt below.", "agent")
        self.terminal.writeline("\u2500" * 50, "sep")
        self.terminal.focus_input()
        self._start_poller()

    def _on_agent_error(self, error: str):
        self.terminal.set_waiting(False)
        self.terminal.writeline(f"[Error] {error}", "error")
        self.terminal.writeline("Check your config and try again.", "error")
        self._start_setup()

    # ── Agent interaction ─────────────────────────────────────────
    def _poll_agent(self):
        if not self.agent_runner:
            return
        result = self.agent_runner.poll()
        if result:
            kind, data = result
            if kind == "response":
                self.terminal.writeline(data, "agent")
                self.terminal.writeline("\u2500" * 40, "sep")
                self.terminal.set_waiting(False)
                self.terminal.focus_input()
                self.editor.check_external_change()
            elif kind == "error":
                self.terminal.writeline(f"[Error] {data}", "error")
                self.terminal.writeline("\u2500" * 40, "sep")
                self.terminal.set_waiting(False)
                self.terminal.focus_input()
            elif kind == "stdout":
                for line in data.split("\n"):
                    line = line.strip()
                    if line:
                        self.terminal.writeline(f"  {line}", "info")
                self.after(100, self._poll_agent)
            elif kind == "stderr":
                for line in data.split("\n"):
                    line = line.strip()
                    if line:
                        self.terminal.writeline(f"  {line}", "error")
                self.after(100, self._poll_agent)
            else:
                self.after(100, self._poll_agent)
        else:
            self.after(100, self._poll_agent)

    def _on_file_open(self, path: str, content: str):
        if self.agent_runner:
            self.agent_runner.set_current_file(path, content)

    def _on_folder_open(self, path: str):
        self.config.workspace_dir = path
        save_config(self.config)
        self.terminal.writeline(f"Workspace set to: {path}", "info")
        self.terminal.writeline("\u2500" * 40, "sep")

    # ── Poller ────────────────────────────────────────────────────
    def _start_poller(self):
        self._poller_running = True
        self._poller()

    def _poller(self):
        if not self._poller_running:
            return
        self.editor.check_external_change()
        self.after(1000, self._poller)

    def _on_close(self):
        self._poller_running = False
        if self.agent_runner:
            self.agent_runner.stop()
        self.destroy()


def run_gui():
    try:
        config = load_config()
        if not config.provider or (config.provider == "ollama" and config.model == "codellama:7b"):
            config = None
    except Exception:
        config = None
    app = BingusGUI(config)
    app.mainloop()
