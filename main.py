import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import http.server
import socketserver
import threading
import socket
import os
import urllib.parse
import webbrowser
from datetime import datetime

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
        self.root.geometry("600x750")  # 再次稍微增加高度
        self.root.minsize(550, 700)
        self.root.configure(bg="#f5f5f7")
        
        self.share_path = ""
        self.is_dir = False
        self.server_thread = None
        self.httpd = None
        self.port = 8080
        self.whitelist = set()  # 存储白名单 IP
        self.whitelist_enabled = tk.BooleanVar(value=False) # 默认关闭

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

        # 白名单控制区
        whitelist_frame = tk.Frame(main_frame, bg="#f5f5f7")
        whitelist_frame.pack(fill="x", pady=10)
        
        ttk.Checkbutton(whitelist_frame, text="开启白名单模式 (仅允许指定IP访问)", variable=self.whitelist_enabled, command=self.on_whitelist_toggle).pack(side=tk.LEFT)
        
        self.ip_entry = ttk.Entry(whitelist_frame, width=15)
        self.ip_entry.pack(side=tk.LEFT, padx=(20, 5))
        self.ip_entry.insert(0, "192.168.1.100")
        
        ttk.Button(whitelist_frame, text="添加IP", command=self.add_to_whitelist, width=8).pack(side=tk.LEFT)

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

        # 日志输出区
        tk.Label(main_frame, text="访问日志:", font=("Microsoft YaHei", 10, "bold"), bg="#f5f5f7").pack(anchor=tk.W, pady=(20, 5))
        self.log_area = scrolledtext.ScrolledText(main_frame, height=10, font=("Consolas", 9), bg="#ffffff", bd=0, highlightthickness=1, highlightbackground="#d2d2d7")
        self.log_area.pack(fill="both", expand=True)
        self.log_area.config(state=tk.DISABLED)

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

    def on_whitelist_toggle(self):
        status = "开启" if self.whitelist_enabled.get() else "关闭"
        self.log_to_ui(f"系统消息: 白名单模式已{status}")
        if self.whitelist_enabled.get() and not self.whitelist:
            self.log_to_ui("警告: 已开启白名单但名单为空，任何人都无法访问！")

    def add_to_whitelist(self):
        ip = self.ip_entry.get().strip()
        if ip:
            self.whitelist.add(ip)
            self.log_to_ui(f"系统消息: 已添加 {ip} 到白名单")
            self.ip_entry.delete(0, tk.END)
        else:
            messagebox.showwarning("提示", "请输入有效的 IP 地址")

    def log_to_ui(self, message):
        """线程安全地在 UI 中打印日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}\n"
        
        def update():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, formatted_msg)
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)
        
        self.root.after(0, update)

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
            share_url = f"http://{local_ip}:{self.port}/{urllib.parse.quote(os.path.basename(self.share_path))}"
            dir_to_serve = os.path.dirname(self.share_path)

        self.link_text.delete(0, tk.END)
        self.link_text.insert(0, share_url)
        self.copy_btn.config(state=tk.NORMAL)
        self.open_btn.config(state=tk.NORMAL)

        def run_server():
            # Using ThreadingHTTPServer to handle multiple concurrent connections
            from http.server import ThreadingHTTPServer
            
            app_instance = self

            class LocalizedHandler(http.server.SimpleHTTPRequestHandler):
                def do_GET(self):
                    # 访问控制校验
                    if app_instance.whitelist_enabled.get():
                        client_ip = self.client_address[0]
                        if client_ip not in app_instance.whitelist:
                            app_instance.log_to_ui(f"拦截访问: 来自 {client_ip} 的请求被拒绝 (不在白名单)")
                            self.send_error(403, "Access Denied: You are not on the whitelist.")
                            return
                    
                    super().do_GET()

                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=dir_to_serve, **kwargs)
                
                def log_message(self, format, *args):
                    # 捕获访问请求并发送到 UI
                    client_ip = self.client_address[0]
                    request_info = args[0] if len(args) > 0 else "Unknown Request"
                    status_code = args[1] if len(args) > 1 else "---"
                    app_instance.log_to_ui(f"{client_ip} - {request_info} [{status_code}]")

            try:
                with ThreadingHTTPServer(("", self.port), LocalizedHandler) as httpd:
                    self.httpd = httpd
                    name = os.path.basename(self.share_path)
                    self.status_var.set(f"● 正在分享: {name} (多连接支持已开启)")
                    httpd.serve_forever()
            except Exception as e:
                self.status_var.set(f"错误: {e}")

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
