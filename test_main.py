"""
测试用例 - 极简秒传
覆盖：工具函数、HTML 解析、HTTP 服务端与客户端下载/预览
"""

import os
import sys
import time
import shutil
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
import http.server

# 确保能导入 main 模块
sys.path.insert(0, os.path.dirname(__file__))

from main import (
    get_local_ip,
    get_all_interfaces,
    format_size,
    DirectoryListParser,
    fetch_file_list,
    download_file,
    download_directory,
    fetch_text_content,
    TEXT_EXTENSIONS,
    url_to_unc_path,
    is_smb_or_file_url,
    list_unc_directory,
    copy_unc_file,
    copy_unc_directory,
)


class TestFormatSize(unittest.TestCase):
    """测试文件大小格式化"""

    def test_bytes(self):
        self.assertEqual(format_size(0), "0.0 B")
        self.assertEqual(format_size(512), "512.0 B")

    def test_kilobytes(self):
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1536), "1.5 KB")

    def test_megabytes(self):
        self.assertEqual(format_size(1048576), "1.0 MB")

    def test_gigabytes(self):
        self.assertEqual(format_size(1073741824), "1.0 GB")

    def test_none_and_negative(self):
        self.assertEqual(format_size(None), "-")
        self.assertEqual(format_size(-1), "-")


class TestGetLocalIp(unittest.TestCase):
    """测试获取本地 IP"""

    def test_returns_ip_string(self):
        ip = get_local_ip()
        self.assertIsInstance(ip, str)
        # 应该是一个合法的 IPv4 地址格式
        parts = ip.split(".")
        self.assertEqual(len(parts), 4)
        for p in parts:
            self.assertTrue(0 <= int(p) <= 255)


class TestGetAllInterfaces(unittest.TestCase):
    """测试获取所有网络接口"""

    def test_returns_list(self):
        interfaces = get_all_interfaces()
        self.assertIsInstance(interfaces, list)
        self.assertTrue(len(interfaces) > 0)

    def test_tuple_format(self):
        interfaces = get_all_interfaces()
        for display_text, ip in interfaces:
            self.assertIsInstance(display_text, str)
            self.assertIsInstance(ip, str)
            # IP 不应以 127 开头
            self.assertFalse(ip.startswith("127."))

    def test_display_text_contains_ip(self):
        interfaces = get_all_interfaces()
        for display_text, ip in interfaces:
            self.assertIn(ip, display_text)


class TestDirectoryListParser(unittest.TestCase):
    """测试 HTML 目录列表解析"""

    SAMPLE_HTML = """
    <!DOCTYPE html>
    <html><body>
    <h1>Directory listing for /</h1>
    <ul>
    <li><a href="..">.. (parent)</a></li>
    <li><a href="docs/">docs/</a></li>
    <li><a href="readme.txt">readme.txt</a></li>
    <li><a href="%E4%B8%AD%E6%96%87%E6%96%87%E4%BB%B6.txt">中文文件.txt</a></li>
    </ul>
    </body></html>
    """

    def test_parse_links(self):
        parser = DirectoryListParser()
        parser.feed(self.SAMPLE_HTML)
        # 应该跳过 ".."
        names = [href for href, _ in parser.links]
        self.assertNotIn("..", names)
        self.assertIn("docs/", names)
        self.assertIn("readme.txt", names)

    def test_chinese_filename(self):
        parser = DirectoryListParser()
        parser.feed(self.SAMPLE_HTML)
        hrefs = [h for h, _ in parser.links]
        self.assertIn("%E4%B8%AD%E6%96%87%E6%96%87%E4%BB%B6.txt", hrefs)


class TestTextExtensions(unittest.TestCase):
    """测试文本扩展名集合"""

    def test_common_text_files(self):
        self.assertIn(".txt", TEXT_EXTENSIONS)
        self.assertIn(".py", TEXT_EXTENSIONS)
        self.assertIn(".json", TEXT_EXTENSIONS)
        self.assertIn(".md", TEXT_EXTENSIONS)

    def test_binary_not_included(self):
        self.assertNotIn(".exe", TEXT_EXTENSIONS)
        self.assertNotIn(".zip", TEXT_EXTENSIONS)
        self.assertNotIn(".jpg", TEXT_EXTENSIONS)


# ─── 集成测试：启动真实的 HTTP 服务器 ────────────────────────
class IntegrationTestBase(unittest.TestCase):
    """集成测试基类：创建临时目录并启动 HTTP 服务器"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="http_share_test_")

        # 创建测试文件
        with open(os.path.join(cls.test_dir, "hello.txt"), "w", encoding="utf-8") as f:
            f.write("Hello, World!\n这是一个测试文件。")

        with open(os.path.join(cls.test_dir, "data.bin"), "wb") as f:
            f.write(os.urandom(2048))

        # 创建子目录和子文件
        sub_dir = os.path.join(cls.test_dir, "subfolder")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "nested.txt"), "w", encoding="utf-8") as f:
            f.write("Nested content 嵌套内容")

        # 启动 HTTP 服务器
        cls.port = 18234  # 使用一个不常见的端口
        handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
            *args, directory=cls.test_dir, **kwargs
        )
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", cls.port), handler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)  # 等服务器就绪

        cls.base_url = f"http://127.0.0.1:{cls.port}/"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.test_dir, ignore_errors=True)


class TestFetchFileList(IntegrationTestBase):
    """测试远程文件列表获取"""

    def test_list_root(self):
        items = fetch_file_list(self.base_url)
        names = [name for name, *_ in items]
        self.assertIn("hello.txt", names)
        self.assertIn("data.bin", names)
        self.assertIn("subfolder", names)

    def test_directory_flag(self):
        items = fetch_file_list(self.base_url)
        for name, is_dir, _, _ in items:
            if name == "subfolder":
                self.assertTrue(is_dir)
            elif name == "hello.txt":
                self.assertFalse(is_dir)

    def test_file_size_populated(self):
        items = fetch_file_list(self.base_url)
        for name, is_dir, size_str, _ in items:
            if name == "data.bin":
                self.assertNotEqual(size_str, "-")  # 2048 字节应该有大小

    def test_list_subdirectory(self):
        sub_url = self.base_url + "subfolder/"
        items = fetch_file_list(sub_url)
        names = [n for n, *_ in items]
        self.assertIn("nested.txt", names)


class TestDownloadFile(IntegrationTestBase):
    """测试单文件下载"""

    def test_download_text_file(self):
        dest = os.path.join(self.test_dir, "_downloaded_hello.txt")
        url = self.base_url + "hello.txt"
        download_file(url, dest)
        self.assertTrue(os.path.exists(dest))
        with open(dest, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Hello, World!", content)
        self.assertIn("测试文件", content)

    def test_download_binary_file(self):
        dest = os.path.join(self.test_dir, "_downloaded_data.bin")
        url = self.base_url + "data.bin"
        download_file(url, dest)
        self.assertTrue(os.path.exists(dest))
        self.assertEqual(os.path.getsize(dest), 2048)

    def test_download_progress_callback(self):
        dest = os.path.join(self.test_dir, "_downloaded_cb.bin")
        url = self.base_url + "data.bin"
        progress_calls = []
        download_file(url, dest, progress_callback=lambda d, t: progress_calls.append((d, t)))
        self.assertTrue(len(progress_calls) > 0)
        # 最后一次的 downloaded 应该等于 total
        last_downloaded, total = progress_calls[-1]
        self.assertEqual(last_downloaded, total)


class TestDownloadDirectory(IntegrationTestBase):
    """测试整个目录递归下载"""

    def test_download_subfolder(self):
        dest_dir = os.path.join(self.test_dir, "_downloaded_subfolder")
        sub_url = self.base_url + "subfolder/"
        download_directory(sub_url, dest_dir)
        nested_path = os.path.join(dest_dir, "nested.txt")
        self.assertTrue(os.path.exists(nested_path))
        with open(nested_path, "r", encoding="utf-8") as f:
            self.assertIn("嵌套内容", f.read())


class TestFetchTextContent(IntegrationTestBase):
    """测试在线文本预览"""

    def test_fetch_text(self):
        url = self.base_url + "hello.txt"
        content = fetch_text_content(url)
        self.assertIn("Hello, World!", content)
        self.assertIn("测试文件", content)

    def test_fetch_max_bytes(self):
        url = self.base_url + "data.bin"
        content = fetch_text_content(url, max_bytes=100)
        # 虽然是 2048 字节，但只读 100 字节
        self.assertTrue(len(content.encode("utf-8", errors="replace")) <= 200)  # 替换字符可能变大，但应远小于 2048


# ─── UNC / file:// 路径工具函数测试 ────────────────────────
class TestUrlToUncPath(unittest.TestCase):
    """测试 file:// URL 转 UNC 路径"""

    def test_file_url_basic(self):
        result = url_to_unc_path("file://192.168.1.5/share/docs")
        self.assertEqual(result, "\\\\192.168.1.5\\share\\docs")

    def test_file_url_with_encoded_chinese(self):
        url = "file://192.168.1.5/%E6%96%87%E4%BB%B6"
        result = url_to_unc_path(url)
        self.assertEqual(result, "\\\\192.168.1.5\\文件")

    def test_unc_passthrough(self):
        result = url_to_unc_path("\\\\192.168.1.5\\share")
        self.assertEqual(result, "\\\\192.168.1.5\\share")

    def test_http_returns_none(self):
        result = url_to_unc_path("http://example.com")
        self.assertIsNone(result)

    def test_strips_whitespace(self):
        result = url_to_unc_path("  file://server/path  ")
        self.assertEqual(result, "\\\\server\\path")


class TestIsSmbOrFileUrl(unittest.TestCase):
    """测试 SMB / file 路径判断"""

    def test_file_url(self):
        self.assertTrue(is_smb_or_file_url("file://192.168.1.5/share"))

    def test_unc_path(self):
        self.assertTrue(is_smb_or_file_url("\\\\192.168.1.5\\share"))

    def test_http_url(self):
        self.assertFalse(is_smb_or_file_url("http://example.com"))

    def test_plain_path(self):
        self.assertFalse(is_smb_or_file_url("C:\\Users\\test"))


class TestListUncDirectory(unittest.TestCase):
    """测试本地/UNC 目录列表读取"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="unc_test_")
        with open(os.path.join(cls.test_dir, "alpha.txt"), "w", encoding="utf-8") as f:
            f.write("Alpha content")
        with open(os.path.join(cls.test_dir, "中文.txt"), "w", encoding="utf-8") as f:
            f.write("中文内容")
        os.makedirs(os.path.join(cls.test_dir, "subdir"))
        with open(os.path.join(cls.test_dir, "subdir", "inner.txt"), "w") as f:
            f.write("inner")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_list_root(self):
        items = list_unc_directory(self.test_dir)
        names = [n for n, *_ in items]
        self.assertIn("alpha.txt", names)
        self.assertIn("中文.txt", names)
        self.assertIn("subdir", names)

    def test_directory_flag(self):
        items = list_unc_directory(self.test_dir)
        for name, is_dir, _, _ in items:
            if name == "subdir":
                self.assertTrue(is_dir)
            elif name == "alpha.txt":
                self.assertFalse(is_dir)

    def test_size_and_time(self):
        items = list_unc_directory(self.test_dir)
        for name, is_dir, size_str, modified_str in items:
            if name == "alpha.txt":
                self.assertNotEqual(size_str, "-")
                self.assertNotEqual(modified_str, "-")

    def test_nonexistent_path(self):
        with self.assertRaises(FileNotFoundError):
            list_unc_directory(os.path.join(self.test_dir, "nonexistent"))


class TestCopyUncFile(unittest.TestCase):
    """测试 UNC 文件复制"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="unc_copy_test_")
        cls.src_file = os.path.join(cls.test_dir, "source.txt")
        with open(cls.src_file, "w", encoding="utf-8") as f:
            f.write("Hello UNC copy! 你好!")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_copy_file(self):
        dest = os.path.join(self.test_dir, "copied.txt")
        copy_unc_file(self.src_file, dest)
        self.assertTrue(os.path.exists(dest))
        with open(dest, "r", encoding="utf-8") as f:
            self.assertIn("Hello UNC copy!", f.read())

    def test_copy_with_progress(self):
        dest = os.path.join(self.test_dir, "copied_cb.txt")
        calls = []
        copy_unc_file(self.src_file, dest, progress_callback=lambda d, t: calls.append((d, t)))
        self.assertTrue(len(calls) > 0)


class TestCopyUncDirectory(unittest.TestCase):
    """测试 UNC 目录递归复制"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="unc_dir_test_")
        cls.src_dir = os.path.join(cls.test_dir, "src")
        os.makedirs(os.path.join(cls.src_dir, "inner"))
        with open(os.path.join(cls.src_dir, "top.txt"), "w") as f:
            f.write("top level")
        with open(os.path.join(cls.src_dir, "inner", "deep.txt"), "w") as f:
            f.write("deep level")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_copy_directory(self):
        dest_dir = os.path.join(self.test_dir, "dst")
        copy_unc_directory(self.src_dir, dest_dir)
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "top.txt")))
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "inner", "deep.txt")))
        with open(os.path.join(dest_dir, "inner", "deep.txt"), "r") as f:
            self.assertEqual(f.read(), "deep level")


if __name__ == "__main__":
    unittest.main(verbosity=2)
