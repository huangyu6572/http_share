import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import http.server
import threading
import socket
import os
import urllib.parse
import urllib.request
import webbrowser
import re
import shutil
from datetime import datetime
from html.parser import HTMLParser
from version import get_version


# ─── 工具函数 ───────────────────────────────────────────────
def get_local_ip():
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _detect_best_ip():
    """检测能联通默认网关的本机 IP（通过 UDP connect 到公网地址）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def get_all_interfaces():
    """获取所有可用的网络接口和对应 IPv4 地址，返回 [(显示文本, ip), ...]
    自动把能联通路由/网关的网卡排在最前面，便于用户零操作即开始分享。
    """
    interfaces = []
    try:
        import psutil
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                    interfaces.append((f"{name}  ({addr.address})", addr.address))
    except ImportError:
        pass
    # 兜底：至少保留默认路由 IP
    if not interfaces:
        ip = get_local_ip()
        interfaces.append((f"默认  ({ip})", ip))
        return interfaces

    # 把能连通网关的网卡排到最前
    best_ip = _detect_best_ip()
    if best_ip:
        interfaces.sort(key=lambda item: (0 if item[1] == best_ip else 1))
    return interfaces


def format_size(size_bytes):
    """把字节数格式化为人类可读的大小"""
    if size_bytes is None or size_bytes < 0:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def url_to_unc_path(url):
    """将 file:// URL 或 SMB 路径转为 Windows UNC 路径
    例如: file://192.168.1.5/share/docs  -> \\\\192.168.1.5\\share\\docs
          \\\\192.168.1.5\\share          -> 原样返回
    """
    url = url.strip()
    if url.startswith("file://"):
        # file://host/path -> \\host\path
        path = url[len("file://"):]
        path = urllib.parse.unquote(path)
        path = path.replace("/", "\\")
        if not path.startswith("\\\\"):
            path = "\\\\" + path
        return path
    if url.startswith("\\\\"):
        return url
    return None  # 不是 file/UNC 路径


def is_smb_or_file_url(url):
    """判断是否是 file:// 或 UNC(\\\\) 路径"""
    url = url.strip()
    return url.startswith("file://") or url.startswith("\\\\")


def list_unc_directory(unc_path):
    """列出 UNC/本地目录的文件，返回 [(name, is_dir, size_str, modified_str), ...]"""
    items = []
    try:
        entries = os.listdir(unc_path)
    except PermissionError:
        raise PermissionError(f"无权限访问: {unc_path}")
    except FileNotFoundError:
        raise FileNotFoundError(f"路径不存在: {unc_path}")

    for entry in sorted(entries, key=lambda x: (not os.path.isdir(os.path.join(unc_path, x)), x.lower())):
        full_path = os.path.join(unc_path, entry)
        is_dir = os.path.isdir(full_path)
        size_str = "-"
        modified_str = "-"
        try:
            stat = os.stat(full_path)
            if not is_dir:
                size_str = format_size(stat.st_size)
            modified_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        items.append((entry, is_dir, size_str, modified_str))
    return items


def copy_unc_file(src_path, dest_path, progress_callback=None):
    """从 UNC 路径复制文件到本地"""
    total = os.path.getsize(src_path)
    copied = 0
    with open(src_path, "rb") as src, open(dest_path, "wb") as dst:
        while True:
            chunk = src.read(8192)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            if progress_callback and total:
                progress_callback(copied, total)


def copy_unc_directory(src_dir, dest_dir, progress_callback=None):
    """递归复制 UNC 目录到本地"""
    os.makedirs(dest_dir, exist_ok=True)
    for entry in os.listdir(src_dir):
        src_path = os.path.join(src_dir, entry)
        dst_path = os.path.join(dest_dir, entry)
        if os.path.isdir(src_path):
            copy_unc_directory(src_path, dst_path, progress_callback)
        else:
            copy_unc_file(src_path, dst_path, progress_callback)
            if progress_callback:
                progress_callback(-1, -1)


# ─── HTTP 目录列表解析器 ─────────────────────────────────────
class DirectoryListParser(HTMLParser):
    """解析 Python SimpleHTTPServer 生成的目录列表 HTML，提取链接名称"""

    def __init__(self):
        super().__init__()
        self.links = []  # [(href, display_text)]
        self._in_a = False
        self._href = ""
        self._text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._in_a = True
            self._text = ""
            for name, value in attrs:
                if name == "href":
                    self._href = value

    def handle_data(self, data):
        if self._in_a:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "a" and self._in_a:
            self._in_a = False
            href = self._href
            text = self._text.strip()
            # 跳过 ../ 上级目录链接
            if text and href and text != ".." and href.rstrip("/") != "..":
                self.links.append((href, text))


def fetch_file_list(base_url):
    """从远程 HTTP 服务器获取文件列表，返回 [(name, is_dir, size_str, modified_str), ...]"""
    if not base_url.endswith("/"):
        base_url += "/"

    req = urllib.request.Request(base_url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    parser = DirectoryListParser()
    parser.feed(html)

    items = []
    for href, display_text in parser.links:
        is_dir = href.endswith("/")
        name = urllib.parse.unquote(href).rstrip("/")
        if not name or name == "..":
            continue

        # 尝试通过 HEAD 请求获取文件大小和修改时间
        size_str = "-"
        modified_str = "-"
        try:
            full_url = urllib.parse.urljoin(base_url, href)
            head_req = urllib.request.Request(full_url, method="HEAD")
            with urllib.request.urlopen(head_req, timeout=5) as head_resp:
                cl = head_resp.getheader("Content-Length")
                if cl and not is_dir:
                    size_str = format_size(int(cl))
                lm = head_resp.getheader("Last-Modified")
                if lm:
                    modified_str = lm
        except Exception:
            pass

        items.append((name, is_dir, size_str, modified_str))

    return items


def download_file(url, dest_path, progress_callback=None):
    """下载单个文件到 dest_path，支持进度回调"""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        total = resp.getheader("Content-Length")
        total = int(total) if total else None
        downloaded = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    progress_callback(downloaded, total)


def download_directory(base_url, dest_dir, progress_callback=None):
    """递归下载整个远程目录到本地 dest_dir"""
    if not base_url.endswith("/"):
        base_url += "/"
    os.makedirs(dest_dir, exist_ok=True)

    items = fetch_file_list(base_url)
    for name, is_dir, _, _ in items:
        item_url = urllib.parse.urljoin(base_url, urllib.parse.quote(name) + ("/" if is_dir else ""))
        local_path = os.path.join(dest_dir, name)
        if is_dir:
            download_directory(item_url, local_path, progress_callback)
        else:
            download_file(item_url, local_path, progress_callback)
            if progress_callback:
                progress_callback(-1, -1)  # 信号：一个文件完成


def fetch_text_content(url, max_bytes=1024 * 512):
    """获取远程文本文件内容（最多读 512KB）"""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read(max_bytes)
    return data.decode("utf-8", errors="replace")


# ─── 分享页 Tab ─────────────────────────────────────────────
class ShareTab:
    """原有的"文件分享"功能，封装到一个 Tab 中"""

    def __init__(self, parent_frame, root):
        self.root = root
        self.share_path = ""
        self.is_dir = False
        self.server_thread = None
        self.httpd = None
        self.port = 8080
        self.whitelist = set()
        self.whitelist_enabled = tk.BooleanVar(value=False)
        self.settings_visible = False
        self.selected_ip = tk.StringVar()

        # 获取网卡列表
        self.interfaces = get_all_interfaces()
        if self.interfaces:
            self.selected_ip.set(self.interfaces[0][0])

        self.setup_ui(parent_frame)

    def setup_ui(self, parent):
        main_frame = tk.Frame(parent, bg="#f5f5f7", padx=30, pady=15)
        main_frame.pack(expand=True, fill="both")

        # 标题
        tk.Label(main_frame, text="快速共享文件", font=("Microsoft YaHei", 18, "bold"),
                 bg="#f5f5f7", fg="#1d1d1f").pack(pady=(0, 5))
        tk.Label(main_frame, text="选择一个文件或目录，局域网内的设备即可访问",
                 font=("Microsoft YaHei", 9), bg="#f5f5f7", fg="#86868b").pack(pady=(0, 15))

        # 按钮区
        btn_frame = tk.Frame(main_frame, bg="#f5f5f7")
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="📄 选择文件", command=self.select_file, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="📁 选择文件夹", command=self.select_folder, width=15).pack(side=tk.LEFT, padx=10)

        # 路径展示区
        path_container = tk.Frame(main_frame, bg="#ffffff", highlightthickness=1,
                                  highlightbackground="#d2d2d7", padx=10, pady=8)
        path_container.pack(fill="x", pady=10)
        self.path_label = tk.Label(path_container, text="等待选择内容...",
                                   font=("Microsoft YaHei", 9), bg="#ffffff", fg="#6e6e73", wraplength=480)
        self.path_label.pack()

        # ⚙ 设置按钮（可折叠）
        self.toggle_btn = tk.Label(main_frame, text="⚙ 展开设置", font=("Microsoft YaHei", 9),
                                   bg="#f5f5f7", fg="#007aff", cursor="hand2")
        self.toggle_btn.pack(anchor=tk.W, pady=(5, 0))
        self.toggle_btn.bind("<Button-1>", lambda e: self.toggle_settings())

        # 设置面板 (默认隐藏)
        self.settings_frame = tk.Frame(main_frame, bg="#eeeef0", highlightthickness=1,
                                       highlightbackground="#d2d2d7", padx=12, pady=10)
        # 不 pack, 初始隐藏

        # 设置项 - 网卡选择
        nic_frame = tk.Frame(self.settings_frame, bg="#eeeef0")
        nic_frame.pack(fill="x", pady=3)
        tk.Label(nic_frame, text="🌐 网卡:", font=("Microsoft YaHei", 9), bg="#eeeef0").pack(side=tk.LEFT)
        nic_values = [item[0] for item in self.interfaces]
        self.nic_combo = ttk.Combobox(nic_frame, textvariable=self.selected_ip,
                                      values=nic_values, state="readonly", width=35)
        self.nic_combo.pack(side=tk.LEFT, padx=8)
        self.nic_combo.bind("<<ComboboxSelected>>", lambda e: self._on_nic_change())

        # 设置项 - 白名单
        wl_frame = tk.Frame(self.settings_frame, bg="#eeeef0")
        wl_frame.pack(fill="x", pady=3)
        ttk.Checkbutton(wl_frame, text="🔒 开启白名单 (仅允许指定IP)",
                        variable=self.whitelist_enabled, command=self.on_whitelist_toggle).pack(side=tk.LEFT)

        wl_input_frame = tk.Frame(self.settings_frame, bg="#eeeef0")
        wl_input_frame.pack(fill="x", pady=3)
        tk.Label(wl_input_frame, text="      允许IP:", font=("Microsoft YaHei", 9), bg="#eeeef0").pack(side=tk.LEFT)
        self.ip_entry = ttk.Entry(wl_input_frame, width=15)
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.ip_entry.insert(0, "192.168.1.100")
        ttk.Button(wl_input_frame, text="添加", command=self.add_to_whitelist, width=6).pack(side=tk.LEFT, padx=3)
        self.wl_list_label = tk.Label(wl_input_frame, text="", font=("Microsoft YaHei", 8),
                                      bg="#eeeef0", fg="#86868b")
        self.wl_list_label.pack(side=tk.LEFT, padx=8)

        # 链接
        tk.Label(main_frame, text="共享链接:", font=("Microsoft YaHei", 10, "bold"),
                 bg="#f5f5f7").pack(anchor=tk.W, pady=(10, 0))
        self.link_text = tk.Entry(main_frame, font=("Consolas", 11), bd=0,
                                  highlightthickness=1, highlightbackground="#d2d2d7", justify="center")
        self.link_text.pack(fill="x", pady=5, ipady=6)

        action_frame = tk.Frame(main_frame, bg="#f5f5f7")
        action_frame.pack(pady=5)
        self.copy_btn = ttk.Button(action_frame, text="📋 复制链接", command=self.copy_link, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=5)
        self.open_btn = ttk.Button(action_frame, text="🌐 浏览器打开", command=self.open_in_browser, state=tk.DISABLED)
        self.open_btn.pack(side=tk.LEFT, padx=5)

        # 日志
        tk.Label(main_frame, text="访问日志:", font=("Microsoft YaHei", 10, "bold"),
                 bg="#f5f5f7").pack(anchor=tk.W, pady=(10, 3))
        self.log_area = scrolledtext.ScrolledText(main_frame, height=8, font=("Consolas", 9),
                                                  bg="#ffffff", bd=0, highlightthickness=1,
                                                  highlightbackground="#d2d2d7")
        self.log_area.pack(fill="both", expand=True)
        self.log_area.config(state=tk.DISABLED)

    # ── 设置面板折叠 ──
    def toggle_settings(self):
        if self.settings_visible:
            self.settings_frame.pack_forget()
            self.toggle_btn.config(text="⚙ 展开设置")
            self.settings_visible = False
        else:
            # 插到 toggle_btn 下方
            self.settings_frame.pack(after=self.toggle_btn, fill="x", pady=(3, 8))
            self.toggle_btn.config(text="⚙ 收起设置")
            self.settings_visible = True

    def _on_nic_change(self):
        """网卡切换后，如果正在分享则重新生成链接"""
        if self.share_path:
            self._update_share_url()
            self.log(f"网卡已切换 → {self._get_selected_ip()}")

    def _get_selected_ip(self):
        """从下拉框获取当前选中的 IP"""
        display = self.selected_ip.get()
        for text, ip in self.interfaces:
            if text == display:
                return ip
        return get_local_ip()

    # ── 业务逻辑 ──
    def select_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.share_path = path
            self.is_dir = False
            self.path_label.config(text=f"文件: {os.path.basename(path)}", fg="black")
            self.start_server()

    def select_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.share_path = path
            self.is_dir = True
            self.path_label.config(text=f"文件夹: {os.path.basename(path)}", fg="blue")
            self.start_server()

    def on_whitelist_toggle(self):
        status = "开启" if self.whitelist_enabled.get() else "关闭"
        self.log(f"系统消息: 白名单模式已{status}")
        if self.whitelist_enabled.get() and not self.whitelist:
            self.log("警告: 已开启白名单但名单为空，任何人都无法访问！")

    def add_to_whitelist(self):
        ip = self.ip_entry.get().strip()
        if ip:
            self.whitelist.add(ip)
            self.log(f"系统消息: 已添加 {ip} 到白名单")
            self.ip_entry.delete(0, tk.END)
            self.wl_list_label.config(text=f"已添加: {', '.join(self.whitelist)}")
        else:
            messagebox.showwarning("提示", "请输入有效的 IP 地址")

    def log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        msg = f"[{ts}] {message}\n"

        def _update():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, msg)
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)

        self.root.after(0, _update)

    def _update_share_url(self):
        """根据当前选中的网卡更新链接"""
        local_ip = self._get_selected_ip()
        if self.is_dir:
            share_url = f"http://{local_ip}:{self.port}/"
        else:
            share_url = f"http://{local_ip}:{self.port}/{urllib.parse.quote(os.path.basename(self.share_path))}"
        self.link_text.delete(0, tk.END)
        self.link_text.insert(0, share_url)

    def start_server(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()

        local_ip = self._get_selected_ip()
        if self.is_dir:
            share_url = f"http://{local_ip}:{self.port}/"
            dir_to_serve = self.share_path
        else:
            share_url = f"http://{local_ip}:{self.port}/{urllib.parse.quote(os.path.basename(self.share_path))}"
            dir_to_serve = os.path.dirname(self.share_path)

        self.link_text.delete(0, tk.END)
        self.link_text.insert(0, share_url)
        self.copy_btn.config(state=tk.NORMAL)
        self.open_btn.config(state=tk.NORMAL)

        tab = self

        def run_server():
            from http.server import ThreadingHTTPServer

            class Handler(http.server.SimpleHTTPRequestHandler):
                def do_GET(self_h):
                    if tab.whitelist_enabled.get():
                        cip = self_h.client_address[0]
                        if cip not in tab.whitelist:
                            tab.log(f"拦截: {cip} 被拒绝 (不在白名单)")
                            self_h.send_error(403, "Access Denied")
                            return
                    super(Handler, self_h).do_GET()

                def __init__(self_h, *a, **kw):
                    super().__init__(*a, directory=dir_to_serve, **kw)

                def log_message(self_h, fmt, *args):
                    cip = self_h.client_address[0]
                    req = args[0] if args else ""
                    code = args[1] if len(args) > 1 else "---"
                    tab.log(f"{cip} - {req} [{code}]")

            try:
                with ThreadingHTTPServer(("", self.port), Handler) as httpd:
                    self.httpd = httpd
                    tab.log(f"服务已启动 → {share_url}")
                    httpd.serve_forever()
            except Exception as e:
                tab.log(f"错误: {e}")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

    def copy_link(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.link_text.get())
        messagebox.showinfo("成功", "链接已复制到剪贴板")

    def open_in_browser(self):
        webbrowser.open(self.link_text.get())


# ─── 下载页 Tab ─────────────────────────────────────────────
TEXT_EXTENSIONS = {
    ".txt", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml",
    ".md", ".csv", ".log", ".ini", ".cfg", ".yaml", ".yml", ".toml",
    ".sh", ".bat", ".cmd", ".c", ".h", ".cpp", ".java", ".go", ".rs",
    ".rb", ".php", ".sql", ".conf", ".env", ".gitignore", ".properties",
}


class DownloadTab:
    """新增的"下载文件"功能 Tab，支持 HTTP 和 file:// / UNC 路径"""

    def __init__(self, parent_frame, root):
        self.root = root
        self.current_url = ""          # 当前正在浏览的 URL / UNC 路径
        self.is_unc = False            # 当前是否为 UNC/file 模式
        self.history = []              # URL 导航历史
        self.download_dir = ""         # 下载保存目录
        self.setup_ui(parent_frame)

    def setup_ui(self, parent):
        main = tk.Frame(parent, bg="#f5f5f7", padx=20, pady=15)
        main.pack(expand=True, fill="both")

        # 标题
        tk.Label(main, text="远程文件浏览与下载", font=("Microsoft YaHei", 18, "bold"),
                 bg="#f5f5f7", fg="#1d1d1f").pack(pady=(0, 5))
        tk.Label(main, text="输入共享链接，浏览并下载文件",
                 font=("Microsoft YaHei", 9), bg="#f5f5f7", fg="#86868b").pack(pady=(0, 10))

        # 地址栏
        addr_frame = tk.Frame(main, bg="#f5f5f7")
        addr_frame.pack(fill="x", pady=5)
        tk.Label(addr_frame, text="地址:", font=("Microsoft YaHei", 10), bg="#f5f5f7").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(addr_frame, font=("Consolas", 10))
        self.url_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=5, ipady=4)
        self.url_entry.insert(0, "http://192.168.1.5:8080/ 或 \\\\192.168.1.5\\share")
        self.url_entry.bind("<Return>", lambda e: self.go())
        self.url_entry.bind("<FocusIn>", self._clear_placeholder)
        ttk.Button(addr_frame, text="访问", command=self.go, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(addr_frame, text="⬆ 上级", command=self.go_up, width=6).pack(side=tk.LEFT, padx=2)

        # 下载目录选择
        save_frame = tk.Frame(main, bg="#f5f5f7")
        save_frame.pack(fill="x", pady=5)
        tk.Label(save_frame, text="保存到:", font=("Microsoft YaHei", 10), bg="#f5f5f7").pack(side=tk.LEFT)
        self.save_label = tk.Label(save_frame, text="(请先选择保存目录)",
                                   font=("Microsoft YaHei", 9), bg="#f5f5f7", fg="#86868b")
        self.save_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="选择目录", command=self.choose_save_dir, width=10).pack(side=tk.RIGHT)

        # 文件列表 Treeview
        cols = ("name", "type", "size", "modified")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=12)
        self.tree.heading("name", text="名称", anchor=tk.W)
        self.tree.heading("type", text="类型", anchor=tk.CENTER)
        self.tree.heading("size", text="大小", anchor=tk.E)
        self.tree.heading("modified", text="修改时间", anchor=tk.W)
        self.tree.column("name", width=250, anchor=tk.W)
        self.tree.column("type", width=60, anchor=tk.CENTER)
        self.tree.column("size", width=80, anchor=tk.E)
        self.tree.column("modified", width=180, anchor=tk.W)
        self.tree.pack(fill="both", expand=True, pady=5)
        self.tree.bind("<Double-1>", self.on_double_click)

        # 右键菜单
        self.ctx_menu = tk.Menu(self.tree, tearoff=0)
        self.ctx_menu.add_command(label="📥 下载", command=self.download_selected)
        self.ctx_menu.add_command(label="👁 在线预览", command=self.preview_selected)
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 操作栏
        op_frame = tk.Frame(main, bg="#f5f5f7")
        op_frame.pack(fill="x", pady=5)
        ttk.Button(op_frame, text="📥 下载选中项", command=self.download_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(op_frame, text="👁 在线预览", command=self.preview_selected).pack(side=tk.LEFT, padx=5)

        # 状态 / 进度
        self.dl_status_var = tk.StringVar(value="就绪")
        tk.Label(main, textvariable=self.dl_status_var, font=("Microsoft YaHei", 8),
                 bg="#f5f5f7", fg="#424245", anchor=tk.W).pack(fill="x")

    # ── 导航 ──
    def _clear_placeholder(self, event=None):
        """清除地址栏占位提示"""
        text = self.url_entry.get()
        if "或" in text:
            self.url_entry.delete(0, tk.END)

    def go(self):
        url = self.url_entry.get().strip()
        if not url or "或" in url:
            return

        if is_smb_or_file_url(url):
            # file:// 或 UNC 路径
            unc_path = url_to_unc_path(url) if url.startswith("file://") else url
            self.is_unc = True
            self.load_unc(unc_path)
        else:
            self.is_unc = False
            if not url.startswith("http"):
                url = "http://" + url
            self.load_url(url)

    def go_up(self):
        if not self.current_url:
            return
        if self.is_unc:
            parent = os.path.dirname(self.current_url.rstrip("\\"))
            if parent and parent != self.current_url:
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, parent)
                self.load_unc(parent)
        else:
            parent = self.current_url.rstrip("/")
            parent = parent.rsplit("/", 1)[0] + "/"
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, parent)
            self.load_url(parent)

    # ── HTTP 模式 ──
    def load_url(self, url):
        self.dl_status_var.set(f"正在加载 {url} ...")
        self.tree.delete(*self.tree.get_children())

        def _work():
            try:
                items = fetch_file_list(url)
                self.current_url = url if url.endswith("/") else url + "/"
                self.is_unc = False
                self.root.after(0, lambda: self._populate(items))
            except Exception as e:
                self.root.after(0, lambda: self.dl_status_var.set(f"加载失败: {e}"))

        threading.Thread(target=_work, daemon=True).start()

    # ── UNC / file:// 模式 ──
    def load_unc(self, unc_path):
        self.dl_status_var.set(f"正在加载 {unc_path} ...")
        self.tree.delete(*self.tree.get_children())

        def _work():
            try:
                items = list_unc_directory(unc_path)
                self.current_url = unc_path
                self.is_unc = True
                self.root.after(0, lambda: self._populate(items))
            except Exception as e:
                self.root.after(0, lambda: self.dl_status_var.set(f"加载失败: {e}"))

        threading.Thread(target=_work, daemon=True).start()

    def _populate(self, items):
        self.tree.delete(*self.tree.get_children())
        for name, is_dir, size_str, modified in items:
            type_str = "📁 目录" if is_dir else "📄 文件"
            self.tree.insert("", tk.END, values=(name, type_str, size_str, modified),
                             tags=("dir" if is_dir else "file",))
        self.dl_status_var.set(f"已加载 {len(items)} 个项目")
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, self.current_url)

    def on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        name = str(item["values"][0])
        tags = item["tags"]
        if "dir" in tags:
            if self.is_unc:
                new_path = os.path.join(self.current_url, name)
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, new_path)
                self.load_unc(new_path)
            else:
                new_url = self.current_url + urllib.parse.quote(name) + "/"
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, new_url)
                self.load_url(new_url)
        else:
            # 双击文件：如果是文本文件就预览，否则下载
            ext = os.path.splitext(name)[1].lower()
            if ext in TEXT_EXTENSIONS:
                self.preview_file(name)
            else:
                self.download_selected()

    # ── 下载 ──
    def choose_save_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.download_dir = d
            self.save_label.config(text=d, fg="black")

    def download_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择要下载的项目")
            return
        if not self.download_dir:
            self.choose_save_dir()
            if not self.download_dir:
                return

        item = self.tree.item(sel[0])
        name = str(item["values"][0])
        is_dir = "dir" in item["tags"]
        dest = os.path.join(self.download_dir, name)

        self.dl_status_var.set(f"正在下载: {name} ...")

        def _work():
            try:
                if self.is_unc:
                    src = os.path.join(self.current_url, name)
                    if is_dir:
                        copy_unc_directory(src, dest)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        copy_unc_file(src, dest)
                else:
                    file_url = self.current_url + urllib.parse.quote(name) + ("/" if is_dir else "")
                    if is_dir:
                        download_directory(file_url, dest)
                    else:
                        download_file(file_url, dest)
                self.root.after(0, lambda: self.dl_status_var.set(f"✅ 下载完成: {dest}"))
                self.root.after(0, lambda: messagebox.showinfo("完成", f"已下载到:\n{dest}"))
            except Exception as e:
                self.root.after(0, lambda: self.dl_status_var.set(f"❌ 下载失败: {e}"))

        threading.Thread(target=_work, daemon=True).start()

    # ── 预览 ──
    def show_context_menu(self, event):
        try:
            self.tree.selection_set(self.tree.identify_row(event.y))
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctx_menu.grab_release()

    def preview_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择要预览的文件")
            return
        item = self.tree.item(sel[0])
        name = str(item["values"][0])
        if "dir" in item["tags"]:
            messagebox.showinfo("提示", "目录不支持预览，请双击进入")
            return
        self.preview_file(name)

    def preview_file(self, name):
        ext = os.path.splitext(name)[1].lower()
        if ext not in TEXT_EXTENSIONS:
            messagebox.showinfo("提示", f"该文件类型 ({ext}) 不支持文本预览，请下载后查看")
            return

        self.dl_status_var.set(f"正在获取: {name} ...")

        def _work():
            try:
                if self.is_unc:
                    full_path = os.path.join(self.current_url, name)
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(512 * 1024)
                else:
                    file_url = self.current_url + urllib.parse.quote(name)
                    content = fetch_text_content(file_url)
                self.root.after(0, lambda: self._show_preview_window(name, content))
                self.root.after(0, lambda: self.dl_status_var.set("就绪"))
            except Exception as e:
                self.root.after(0, lambda: self.dl_status_var.set(f"预览失败: {e}"))

        threading.Thread(target=_work, daemon=True).start()

    def _show_preview_window(self, title, content):
        win = tk.Toplevel(self.root)
        win.title(f"预览 - {title}")
        win.geometry("700x500")
        text_area = scrolledtext.ScrolledText(win, font=("Consolas", 10), wrap=tk.WORD)
        text_area.pack(fill="both", expand=True)
        text_area.insert("1.0", content)
        text_area.config(state=tk.DISABLED)


# ─── 主应用 ─────────────────────────────────────────────────
class HttpShareApp:
    def __init__(self, root):
        self.root = root
        self.version = get_version()
        self.root.title(f"🚀 极简秒传 v{self.version} - 局域网分享 & 下载")
        self.root.geometry("680x780")
        self.root.minsize(620, 700)
        self.root.configure(bg="#f5f5f7")

        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TButton", font=("Microsoft YaHei", 10), padding=8)

        # Tab 美化：选中白底突出，未选中灰底后退
        self.style.configure("TNotebook", background="#f5f5f7", borderwidth=0, tabmargins=[8, 5, 8, 0])
        self.style.configure("TNotebook.Tab", font=("Microsoft YaHei", 11, "bold"), padding=[24, 10],
                             background="#d2d2d7", foreground="#6e6e73", borderwidth=0)
        self.style.map("TNotebook.Tab",
                       background=[("selected", "#ffffff"), ("!selected", "#d2d2d7")],
                       foreground=[("selected", "#007aff"), ("!selected", "#6e6e73")],
                       expand=[("selected", [0, 3, 0, 0])],  # 选中 Tab 向上凸出 3px
                       padding=[("selected", [24, 12])])

        # 状态栏（放在最底部）
        self.status_var = tk.StringVar(value=f"v{self.version} | 准备就绪")
        status_bar = tk.Label(root, textvariable=self.status_var, bd=0, bg="#e8e8ed",
                              fg="#424245", font=("Microsoft YaHei", 8), anchor=tk.W, padx=10, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Tab 容器
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=(10, 0))

        share_frame = tk.Frame(self.notebook, bg="#f5f5f7")
        download_frame = tk.Frame(self.notebook, bg="#f5f5f7")

        self.notebook.add(share_frame, text="  📤 分享  ")
        self.notebook.add(download_frame, text="  📥 下载  ")

        # 讲解说明 tab
        explain_frame = tk.Frame(self.notebook, bg="#f5f5f7")
        self.notebook.add(explain_frame, text="  📘 讲解说明  ")
        tk.Label(explain_frame, text="欢迎使用应用！这里是讲解说明。", bg="#f5f5f7", font=("Microsoft YaHei", 10)).pack(pady=20)

        self.share_tab = ShareTab(share_frame, root)
        self.download_tab = DownloadTab(download_frame, root)


if __name__ == "__main__":
    root = tk.Tk()
    app = HttpShareApp(root)
    root.mainloop()
