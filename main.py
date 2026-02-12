import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import http.server
import socketserver
import threading
import socket
import os
import urllib.parse
import webbrowser

class ShareServer(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # We'll set directory dynamically in the instance or use default
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass

class HttpShareApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 极简秒传 - 局域网分享")
        self.root.geometry("600x520")  # 增加高度，防止内容被遮挡
        self.root.minsize(550, 500)     # 设置最小尺寸
        self.root.configure(bg="#f5f5f7")  # 浅灰色背景
        
        # 设置 DPI 自适应，防止在高分屏下模糊
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # 自定义样式
        self.style.configure("TButton", font=("Microsoft YaHei", 10), padding=10)
        self.style.configure("Main.TLabel", background="#f5f5f7", font=("Microsoft YaHei", 12))
        self.style.configure("Path.TLabel", background="#ffffff", font=("Microsoft YaHei", 9), relief="flat")
        
        self.share_path = ""
        self.is_dir = False
        self.server_thread = None
        self.httpd = None
        self.port = 8080

        self.setup_ui()

    def setup_ui(self):
        # 主容器
        main_frame = tk.Frame(self.root, bg="#f5f5f7", padx=30, pady=20) # 减小垂直内边距
        main_frame.pack(expand=True, fill="both")

        # 标题
        title_label = tk.Label(main_frame, text="快速共享文件", font=("Microsoft YaHei", 20, "bold"), bg="#f5f5f7", fg="#1d1d1f")
        title_label.pack(pady=(0, 10))
        
        desc_label = tk.Label(main_frame, text="选择一个文件或目录，局域网内的设备即可访问", font=("Microsoft YaHei", 10), bg="#f5f5f7", fg="#86868b")
        desc_label.pack(pady=(0, 20)) # 减小间距

        # 按钮区
        btn_frame = tk.Frame(main_frame, bg="#f5f5f7")
        btn_frame.pack(pady=10)

        self.file_btn = ttk.Button(btn_frame, text="📄 选择文件", command=self.select_file, width=15)
        self.file_btn.pack(side=tk.LEFT, padx=10)

        self.dir_btn = ttk.Button(btn_frame, text="📁 选择文件夹", command=self.select_folder, width=15)
        self.dir_btn.pack(side=tk.LEFT, padx=10)

        # 路径展示区 (带圆角感官的 Frame)
        path_container = tk.Frame(main_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#d2d2d7", padx=10, pady=10)
        path_container.pack(fill="x", pady=15) # 减小间距
        
        self.path_label = tk.Label(path_container, text="等待选择内容...", font=("Microsoft YaHei", 9), bg="#ffffff", fg="#6e6e73", wraplength=480)
        self.path_label.pack()

        # 链接展示区
        link_frame = tk.Frame(main_frame, bg="#f5f5f7")
        link_frame.pack(fill="x", pady=5)
        
        tk.Label(link_frame, text="共享链接:", font=("Microsoft YaHei", 10, "bold"), bg="#f5f5f7").pack(side=tk.LEFT)
        
        self.link_text = tk.Entry(main_frame, font=("Consolas", 11), bd=0, highlightthickness=1, highlightbackground="#d2d2d7", justify='center')
        self.link_text.pack(fill="x", pady=5, ipady=8) # 减小间距
        
        # 操作区
        action_frame = tk.Frame(main_frame, bg="#f5f5f7")
        action_frame.pack(pady=10)

        self.copy_btn = ttk.Button(action_frame, text="📋 复制链接", command=self.copy_link, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=5)

        self.open_btn = ttk.Button(action_frame, text="🌐 浏览器打开", command=self.open_in_browser, state=tk.DISABLED)
        self.open_btn.pack(side=tk.LEFT, padx=5)

        # 状态栏
        self.status_var = tk.StringVar(value="准备就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=0, bg="#e8e8ed", fg="#424245", font=("Microsoft YaHei", 8), anchor=tk.W, padx=10, pady=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

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

    def start_server(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()

        local_ip = self.get_local_ip()
        
        # Determine the base URL
        if self.is_dir:
            share_url = f"http://{local_ip}:{self.port}/"
            dir_to_serve = self.share_path
        else:
            # For a single file, we serve its parent directory and point to the file
            share_url = f"http://{local_ip}:{self.port}/{urllib.parse.quote(os.path.basename(self.share_path))}"
            dir_to_serve = os.path.dirname(self.share_path)

        self.link_text.delete(0, tk.END)
        self.link_text.insert(0, share_url)
        self.copy_btn.config(state=tk.NORMAL)
        self.open_btn.config(state=tk.NORMAL)

        def run_server():
            # Create a localized handler that always serves dir_to_serve
            class LocalizedHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=dir_to_serve, **kwargs)
                
                def log_message(self, format, *args):
                    pass

            with socketserver.TCPServer(("", self.port), LocalizedHandler) as httpd:
                self.httpd = httpd
                name = os.path.basename(self.share_path)
                self.status_var.set(f"● 正在分享: {name}")
                httpd.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

    def copy_link(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.link_text.get())
        messagebox.showinfo("成功", "链接已复制到剪贴板")

    def open_in_browser(self):
        webbrowser.open(self.link_text.get())

if __name__ == "__main__":
    root = tk.Tk()
    app = HttpShareApp(root)
    root.mainloop()
