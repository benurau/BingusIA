import asyncio
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
from pathlib import Path

from bingus_ia.core.agent import Agent
from bingus_ia.core.config import load_config, save_config
from bingus_ia.core.types import AgentConfig, Role


BG = "#1e1e1e"
BG2 = "#252526"
FG = "#cccccc"
FG2 = "#969696"
INPUT_BG = "#3c3c3c"
SEL_BG = "#264f78"
ACCENT = "#007acc"
BORDER = "#3c3c3c"
SCROLL_BG = "#1e1e1e"
SCROLL_FG = "#424242"
TERMINAL_BG = "#1e1e1e"
EDITOR_BG = "#1e1e1e"
LINENUM_BG = "#252526"


def apply_theme(widget):
    for child in widget.winfo_children():
        cls = child.winfo_class()
        if cls == "Frame":
            child.configure(bg=BG)
        elif cls == "Label":
            child.configure(bg=BG, fg=FG)
        elif cls == "Button":
            child.configure(bg=BG2, fg=FG, activebackground=BG,
                            activeforeground=FG, relief=tk.FLAT,
                            bd=1, highlightbackground=BORDER)
        elif cls == "Entry":
            child.configure(bg=INPUT_BG, fg=FG, insertbackground=FG,
                            relief=tk.FLAT, bd=1, highlightbackground=BORDER,
                            highlightcolor=ACCENT)
        elif cls == "Text" or cls == "ScrolledText":
            child.configure(bg=EDITOR_BG, fg=FG, insertbackground=FG,
                            selectbackground=SEL_BG, relief=tk.FLAT, bd=1)
        elif cls == "PanedWindow":
            child.configure(bg=BG2, sashrelief=tk.FLAT, sashwidth=3)
        elif cls == "Listbox":
            child.configure(bg=INPUT_BG, fg=FG, selectbackground=SEL_BG,
                            relief=tk.FLAT, bd=1)
        elif cls == "Checkbutton":
            child.configure(bg=BG, fg=FG, selectcolor=BG2,
                            activebackground=BG, activeforeground=FG)
        apply_theme(child)


def apply_theme_to_window(widget):
    widget.configure(bg=BG)
    apply_theme(widget)


class StartupDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.title("Bingus IA — Setup")
        self.geometry("520x480")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=BG)

        self.result: AgentConfig | None = None

        frame = tk.Frame(self, bg=BG, padx=24, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Bingus IA Setup", font=("Segoe UI", 16, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", pady=(0, 20))

        tk.Label(frame, text="Provider", font=("Segoe UI", 10),
                 bg=BG, fg=FG2, anchor="w").pack(fill=tk.X)
        self.provider_var = tk.StringVar(value="ollama")
        provider_menu = ttk.Combobox(frame, textvariable=self.provider_var,
                                     values=["ollama", "openai", "anthropic", "opencode"],
                                     state="readonly", font=("Segoe UI", 10))
        provider_menu.pack(fill=tk.X, pady=(2, 12))
        provider_menu.bind("<<ComboboxSelected>>", self._on_provider_change)

        self.fields_frame = tk.Frame(frame, bg=BG)
        self.fields_frame.pack(fill=tk.X)

        tk.Label(frame, text="Model", font=("Segoe UI", 10),
                 bg=BG, fg=FG2, anchor="w").pack(fill=tk.X, pady=(12, 0))
        self.model_var = tk.StringVar(value="codellama:7b")
        tk.Entry(frame, textvariable=self.model_var, font=("Consolas", 10),
                 bg=INPUT_BG, fg=FG, insertbackground=FG, relief=tk.FLAT,
                 highlightbackground=BORDER, highlightcolor=ACCENT).pack(fill=tk.X, pady=(2, 12))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(16, 0))

        tk.Button(btn_frame, text="Start", command=self._on_start,
                  font=("Segoe UI", 10, "bold"), bg=ACCENT, fg="white",
                  activebackground="#005999", activeforeground="white",
                  relief=tk.FLAT, padx=20, pady=4, cursor="hand2").pack(side=tk.RIGHT)

        tk.Button(btn_frame, text="Cancel", command=self.destroy,
                  font=("Segoe UI", 10), bg=BG2, fg=FG,
                  activebackground=BG, activeforeground=FG,
                  relief=tk.FLAT, padx=16, pady=4).pack(side=tk.RIGHT, padx=(0, 8))

        self._on_provider_change()

    def _clear_fields(self):
        for w in self.fields_frame.winfo_children():
            w.destroy()

    def _on_provider_change(self, event=None):
        self._clear_fields()
        provider = self.provider_var.get()
        if provider == "ollama":
            self._build_ollama_fields()
        elif provider == "opencode":
            self._build_api_fields("https://opencode.ai/zen/v1", "big-pickle")
        elif provider == "openai":
            self._build_api_fields("https://api.openai.com/v1", "gpt-4o")
        elif provider == "anthropic":
            self._build_api_fields("https://api.anthropic.com/v1", "claude-sonnet-4-20250514")

    def _build_ollama_fields(self):
        self._ollama_url_var = tk.StringVar(value="http://localhost:11434")
        self._add_field("Ollama URL", self._ollama_url_var, "http://localhost:11434")
        tk.Button(self.fields_frame, text="Fetch Models",
                  command=self._fetch_ollama_models,
                  font=("Segoe UI", 9), bg=BG2, fg=FG,
                  activebackground=BG, activeforeground=FG,
                  relief=tk.FLAT).pack(anchor="w", pady=(4, 0))
        self._model_list_var = tk.StringVar()
        self._model_list = tk.Listbox(self.fields_frame, height=5,
                                       font=("Consolas", 9), bg=INPUT_BG,
                                       fg=FG, selectbackground=SEL_BG,
                                       relief=tk.FLAT, highlightbackground=BORDER)
        self._model_list.pack(fill=tk.X, pady=(6, 0))
        self._model_list.bind("<<ListboxSelect>>", self._on_model_select)

    def _build_api_fields(self, default_url: str, default_model: str):
        self._api_url_var = tk.StringVar(value=default_url)
        self._api_key_var = tk.StringVar(value="")
        self._add_field("API Base URL", self._api_url_var, default_url)
        self._add_field("API Key", self._api_key_var, "sk-...")
        self.model_var.set(default_model)

    def _add_field(self, label: str, var: tk.StringVar, placeholder: str):
        row = tk.Frame(self.fields_frame, bg=BG)
        row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(row, text=label, font=("Segoe UI", 9),
                 bg=BG, fg=FG2, width=14, anchor="w").pack(side=tk.LEFT)
        tk.Entry(row, textvariable=var, font=("Consolas", 9),
                 bg=INPUT_BG, fg=FG, insertbackground=FG,
                 relief=tk.FLAT, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _fetch_ollama_models(self):
        url = self._ollama_url_var.get().strip()
        if not url:
            return
        self._model_list.delete(0, tk.END)
        self._model_list.insert(tk.END, "Loading...")
        threading.Thread(target=self._do_fetch_models, args=(url,),
                         daemon=True).start()

    def _do_fetch_models(self, url: str):
        try:
            import httpx
            resp = httpx.get(f"{url.rstrip('/')}/api/tags", timeout=10)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                names = [m.get("name", m.get("model", "")) for m in models]
                names = [n for n in names if n]
                self.after(0, self._populate_model_list, names)
            else:
                self.after(0, self._populate_model_list, [])
        except Exception as e:
            self.after(0, self._populate_model_list, [], str(e))

    def _populate_model_list(self, names: list[str], error: str = ""):
        self._model_list.delete(0, tk.END)
        if error:
            self._model_list.insert(tk.END, f"Error: {error}")
            return
        if not names:
            self._model_list.insert(tk.END, "No models found")
            return
        for n in names:
            self._model_list.insert(tk.END, n)

    def _on_model_select(self, event=None):
        sel = self._model_list.curselection()
        if sel:
            self.model_var.set(self._model_list.get(sel[0]))

    def _on_start(self):
        provider = self.provider_var.get()
        model = self.model_var.get().strip()

        cfg = AgentConfig()
        cfg.provider = provider
        cfg.model = model

        if provider == "ollama":
            url = getattr(self, "_ollama_url_var", tk.StringVar()).get().strip()
            if url:
                cfg.ollama_base_url = url
        else:
            key = getattr(self, "_api_key_var", tk.StringVar()).get().strip()
            if key:
                cfg.api_key = key
            url = getattr(self, "_api_url_var", tk.StringVar()).get().strip()
            if url:
                cfg.api_base_url = url

        if not cfg.model:
            messagebox.showerror("Error", "Please select a model", parent=self)
            return

        if provider != "ollama" and not cfg.api_key:
            if not messagebox.askyesno("No API Key",
                                       "No API key provided. Continue anyway?",
                                       parent=self):
                return

        self.result = cfg
        save_config(cfg)
        self.destroy()


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
        try:
            self.agent = Agent(self.config)
            self.output_queue.put(("ready", ""))
        except Exception as e:
            self.output_queue.put(("error", f"Agent init failed: {e}"))
            return
        while self._running:
            try:
                prompt = self.input_queue.get(timeout=0.2)
                if prompt is None:
                    break
                result = self._loop.run_until_complete(self.agent.run(prompt))
                self.output_queue.put(("response", result))
            except queue.Empty:
                continue
            except Exception as e:
                self.output_queue.put(("error", str(e)))
        self._loop.run_until_complete(self.agent.close())
        self._loop.close()

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

    def stop(self):
        self._running = False
        self.input_queue.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout=5)


class TerminalPanel(tk.Frame):
    def __init__(self, parent: tk.Widget, agent_runner: AgentRunner,
                 on_agent_done=None):
        super().__init__(parent, bg=BG)
        self.agent_runner = agent_runner
        self.on_agent_done = on_agent_done
        self._waiting = False
        self._build_ui()

    def _build_ui(self):
        header = tk.Label(self, text="TERMINAL", font=("Segoe UI", 9, "bold"),
                          bg=BG2, fg=FG, anchor="w", padx=8, pady=4)
        header.pack(fill=tk.X)

        self.output_area = tk.Text(self, wrap=tk.WORD, font=("Consolas", 10),
                                   bg=TERMINAL_BG, fg=FG, insertbackground=FG,
                                   state=tk.DISABLED, relief=tk.FLAT,
                                   selectbackground=SEL_BG, padx=6, pady=4)
        self.output_area.pack(fill=tk.BOTH, expand=True)

        scroll = tk.Scrollbar(self.output_area, orient=tk.VERTICAL,
                              bg=SCROLL_BG, troughcolor=SCROLL_BG,
                              activebackground=SCROLL_FG, elementborderwidth=0)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_area.config(yscrollcommand=scroll.set)
        scroll.config(command=self.output_area.yview)

        input_frame = tk.Frame(self, bg=BG)
        input_frame.pack(fill=tk.X, pady=(0, 0))

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(input_frame, textvariable=self.input_var,
                                    font=("Consolas", 10), bg=INPUT_BG, fg=FG,
                                    insertbackground=FG, relief=tk.FLAT,
                                    highlightbackground=BORDER, highlightcolor=ACCENT)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 0))
        self.input_entry.bind("<Return>", self._on_submit)

        self.send_btn = tk.Button(input_frame, text="Send", command=self._on_submit,
                                  font=("Segoe UI", 9), bg=ACCENT, fg="white",
                                  activebackground="#005999", activeforeground="white",
                                  relief=tk.FLAT, padx=12, pady=2, cursor="hand2")
        self.send_btn.pack(side=tk.RIGHT)

        self._setup_tags()

    def _setup_tags(self):
        self.output_area.tag_config("user", foreground="#569CD6")
        self.output_area.tag_config("agent", foreground="#6A9955")
        self.output_area.tag_config("error", foreground="#F44747")
        self.output_area.tag_config("info", foreground="#969696")
        self.output_area.tag_config("prompt", foreground="#DCDCAA")
        self.output_area.tag_config("sep", foreground="#3c3c3c")

    def _on_submit(self, event=None):
        prompt = self.input_var.get().strip()
        if not prompt or self._waiting:
            return
        self._waiting = True
        self._toggle_input(False)
        self._append_output(f">>> {prompt}\n", "user")
        self.input_var.set("")
        self.agent_runner.submit(prompt)
        self.after(100, self._poll_agent)

    def _poll_agent(self):
        result = self.agent_runner.poll()
        if result:
            kind, data = result
            if kind == "response":
                self._append_output(f"{data}\n", "agent")
                self._append_output("─" * 40 + "\n", "sep")
                self._waiting = False
                self._toggle_input(True)
                self.input_entry.focus_set()
                if self.on_agent_done:
                    self.on_agent_done()
            elif kind == "error":
                self._append_output(f"[Error] {data}\n", "error")
                self._append_output("─" * 40 + "\n", "sep")
                self._waiting = False
                self._toggle_input(True)
                self.input_entry.focus_set()
            else:
                self.after(100, self._poll_agent)
        else:
            self.after(100, self._poll_agent)

    def _toggle_input(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.input_entry.config(state=state)
        self.send_btn.config(state=state)

    def _append_output(self, text: str, tag: str = ""):
        self.output_area.config(state=tk.NORMAL)
        self.output_area.insert(tk.END, text, tag)
        self.output_area.see(tk.END)
        self.output_area.config(state=tk.DISABLED)

    def append_info(self, text: str):
        self._append_output(text + "\n", "info")


class EditorPanel(tk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=BG)
        self._filepath: str | None = None
        self._mtime: float = 0.0
        self._modified = False
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG2)
        header.pack(fill=tk.X)

        self.file_label = tk.Label(header, text="EDITOR (no file open)",
                                   font=("Segoe UI", 9, "bold"),
                                   bg=BG2, fg=FG, anchor="w", padx=8, pady=4)
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_font = ("Segoe UI", 8)
        btn_frame = tk.Frame(header, bg=BG2)
        btn_frame.pack(side=tk.RIGHT, padx=4)

        self.open_btn = tk.Button(btn_frame, text="Open", command=self._open_file,
                                  font=btn_font, bg=BG2, fg=FG,
                                  activebackground=BG, activeforeground=FG,
                                  relief=tk.FLAT, padx=6, pady=1, cursor="hand2")
        self.open_btn.pack(side=tk.LEFT, padx=1)

        self.save_btn = tk.Button(btn_frame, text="Save", command=self._save_file,
                                  font=btn_font, bg=BG2, fg=FG,
                                  activebackground=BG, activeforeground=FG,
                                  relief=tk.FLAT, padx=6, pady=1, cursor="hand2",
                                  state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=1)

        self.reload_btn = tk.Button(btn_frame, text="Reload", command=self._reload_file,
                                    font=btn_font, bg=BG2, fg=FG,
                                    activebackground=BG, activeforeground=FG,
                                    relief=tk.FLAT, padx=6, pady=1, cursor="hand2",
                                    state=tk.DISABLED)
        self.reload_btn.pack(side=tk.LEFT, padx=1)

        editor_frame = tk.Frame(self, bg=EDITOR_BG)
        editor_frame.pack(fill=tk.BOTH, expand=True)

        self.editor = tk.Text(editor_frame, wrap=tk.WORD, font=("Consolas", 10),
                              bg=EDITOR_BG, fg=FG, insertbackground=FG,
                              relief=tk.FLAT, selectbackground=SEL_BG,
                              padx=8, pady=4, undo=True)
        self.editor.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scroll = tk.Scrollbar(editor_frame, orient=tk.VERTICAL,
                              bg=SCROLL_BG, troughcolor=SCROLL_BG,
                              activebackground=SCROLL_FG, elementborderwidth=0)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor.config(yscrollcommand=scroll.set)
        scroll.config(command=self.editor.yview)

        self.editor.bind("<<Modified>>", self._on_modified)

    def _open_file(self, path: str | None = None):
        if path is None:
            path = filedialog.askopenfilename(
                title="Open File",
                filetypes=[("All Files", "*.*"), ("Python", "*.py"),
                           ("Text", "*.txt"), ("Markdown", "*.md")],
            )
        if not path:
            return
        self._filepath = path
        self._load_file_content()
        try:
            self._mtime = os.path.getmtime(path)
        except OSError:
            self._mtime = 0.0
        self._modified = False
        self.file_label.config(text=f"EDITOR: {Path(path).name}")
        self.save_btn.config(state=tk.NORMAL)
        self.reload_btn.config(state=tk.NORMAL)

    def _load_file_content(self):
        try:
            with open(self._filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", content)
        self.editor.edit_reset()
        self.editor.mark_set(tk.INSERT, "1.0")

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
        if self._modified:
            if not messagebox.askyesno("Unsaved Changes",
                                       "Reload will lose unsaved changes. Continue?"):
                return
        self._load_file_content()
        try:
            self._mtime = os.path.getmtime(self._filepath)
        except OSError:
            self._mtime = 0.0
        self._modified = False

    def _on_modified(self, event=None):
        if self.editor.edit_modified():
            self._modified = True
            self.editor.edit_modified(False)

    def check_external_change(self):
        if not self._filepath or not os.path.exists(self._filepath):
            return
        try:
            current_mtime = os.path.getmtime(self._filepath)
        except OSError:
            return
        if current_mtime != self._mtime:
            self._mtime = current_mtime
            if self._modified:
                self.file_label.config(
                    text=f"EDITOR: {Path(self._filepath).name} [ext]"
                )
            else:
                self._load_file_content()

    @property
    def current_file(self) -> str | None:
        return self._filepath


class FileExplorer(tk.Frame):
    def __init__(self, parent: tk.Widget, editor: EditorPanel):
        super().__init__(parent, bg=BG)
        self.editor = editor
        self._root_path: str | None = None
        self._build_ui()

    def _build_ui(self):
        header = tk.Label(self, text="EXPLORER", font=("Segoe UI", 9, "bold"),
                          bg=BG2, fg=FG, anchor="w", padx=8, pady=4)
        header.pack(fill=tk.X)

        btn_frame = tk.Frame(self, bg=BG2)
        btn_frame.pack(fill=tk.X)

        self.folder_btn = tk.Button(btn_frame, text="Open Folder",
                                    command=self._open_folder,
                                    font=("Segoe UI", 8), bg=BG2, fg=FG,
                                    activebackground=BG, activeforeground=FG,
                                    relief=tk.FLAT, padx=6, pady=1, cursor="hand2")
        self.folder_btn.pack(side=tk.LEFT, padx=4, pady=2)

        self.refresh_btn = tk.Button(btn_frame, text="Refresh",
                                     command=self._refresh_tree,
                                     font=("Segoe UI", 8), bg=BG2, fg=FG,
                                     activebackground=BG, activeforeground=FG,
                                     relief=tk.FLAT, padx=6, pady=1, cursor="hand2")
        self.refresh_btn.pack(side=tk.LEFT, padx=2, pady=2)

        tree_frame = tk.Frame(self, bg=EDITOR_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=EDITOR_BG, foreground=FG,
                        fieldbackground=EDITOR_BG, font=("Consolas", 9),
                        rowheight=22)
        style.configure("Treeview.Item", padding=(2, 0))
        style.map("Treeview", background=[("selected", SEL_BG)],
                  foreground=[("selected", FG)])
        style.configure("Treeview.Heading", background=BG2, foreground=FG,
                        font=("Segoe UI", 8), relief=tk.FLAT)

        self.tree = ttk.Treeview(tree_frame, show="tree", columns=(),
                                 style="Treeview")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = tk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                              bg=SCROLL_BG, troughcolor=SCROLL_BG,
                              activebackground=SCROLL_FG, elementborderwidth=0)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scroll.set)
        scroll.config(command=self.tree.yview)

        self.tree.bind("<Double-1>", self._on_item_double_click)

    def _open_folder(self):
        path = filedialog.askdirectory(title="Open Folder")
        if not path:
            return
        self._root_path = path
        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self._root_path:
            return
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
            node_id = self.tree.insert(parent_id, tk.END, text=name,
                                       open=False,
                                       tags=("dir" if is_dir else "file"))
            self.tree.item(node_id, values=(full,))
            if is_dir:
                self._populate_tree(node_id, full)

    def _on_item_double_click(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        full_path = self.tree.item(item, "values")
        if not full_path:
            return
        path = full_path[0]
        if os.path.isfile(path):
            self.editor._open_file(path)


class BingusGUI(tk.Tk):
    def __init__(self, config: AgentConfig | None = None):
        super().__init__()
        self.title("Bingus IA — AI Programming Assistant")
        self.geometry("1500x850")
        self.minsize(1000, 500)
        self.configure(bg=BG)

        if config is None:
            config = self._show_startup_dialog()
            if config is None:
                self.destroy()
                return

        self.agent_runner = AgentRunner(config)
        self._build_ui()
        self._start_poller()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        config_str = (
            f"Provider: {config.provider}  |  "
            f"Model: {config.model}  |  "
            f"Workspace: {config.workspace_dir}"
        )
        self.terminal.append_info(config_str)
        self.terminal.append_info("─" * 50)

    def _show_startup_dialog(self) -> AgentConfig | None:
        dialog = StartupDialog(self)
        self.wait_window(dialog)
        return dialog.result

    def _build_ui(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BG2,
                               sashrelief=tk.FLAT, sashwidth=3)
        paned.pack(fill=tk.BOTH, expand=True)

        self.terminal = TerminalPanel(paned, self.agent_runner,
                                      on_agent_done=self._on_agent_done)
        paned.add(self.terminal, stretch="always", width=500)

        self.editor = EditorPanel(paned)
        paned.add(self.editor, stretch="always", width=550)

        self.explorer = FileExplorer(paned, self.editor)
        paned.add(self.explorer, stretch="never", width=220)

    def _start_poller(self):
        self._poller_running = True
        self._poller()

    def _poller(self):
        if not self._poller_running:
            return
        self.editor.check_external_change()
        self.after(1000, self._poller)

    def _on_agent_done(self):
        self.editor.check_external_change()

    def _on_close(self):
        self._poller_running = False
        self.agent_runner.stop()
        self.destroy()


def run_gui():
    try:
        config = load_config()
        if config.provider == "ollama" and config.model == "codellama:7b":
            config = None
    except Exception:
        config = None

    app = BingusGUI(config)
    app.mainloop()
