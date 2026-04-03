"""
构建脚本 - 自动递增 BUILD 版本号并调用 PyInstaller 打包
用法: python build.py
"""

import re
import subprocess
import sys
import os

VERSION_FILE = os.path.join(os.path.dirname(__file__), "version.py")
APP_NAME = "极简分享"
MAIN_SCRIPT = "main.py"


def read_version():
    """读取当前版本号"""
    info = {}
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^(MAJOR|MINOR|BUILD)\s*=\s*(\d+)", line)
            if m:
                info[m.group(1)] = int(m.group(2))
    return info["MAJOR"], info["MINOR"], info["BUILD"]


def bump_build(major, minor, build):
    """将 BUILD +1 写回 version.py"""
    new_build = build + 1
    content = (
        "# 版本信息 - 由 build.py 自动更新，请勿手动修改 build 号\n"
        f"MAJOR = {major}\n"
        f"MINOR = {minor}\n"
        f"BUILD = {new_build}\n"
        "\n"
        "def get_version():\n"
        '    return f"{MAJOR}.{MINOR}.{BUILD}"\n'
    )
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    return major, minor, new_build


def run_pyinstaller(version_str):
    """调用 PyInstaller 打包"""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", f"{APP_NAME}_v{version_str}",
        MAIN_SCRIPT,
    ]
    print(f">>> 执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=os.path.dirname(__file__) or ".")
    return result.returncode


def main():
    major, minor, build = read_version()
    print(f"当前版本: {major}.{minor}.{build}")

    major, minor, new_build = bump_build(major, minor, build)
    version_str = f"{major}.{minor}.{new_build}"
    print(f"新版本号: {version_str}")

    print("开始打包...")
    rc = run_pyinstaller(version_str)
    if rc == 0:
        print(f"\n✅ 打包成功! 输出: dist/{APP_NAME}_v{version_str}.exe")
    else:
        print(f"\n❌ 打包失败, 退出码: {rc}")
        sys.exit(rc)


if __name__ == "__main__":
    main()
