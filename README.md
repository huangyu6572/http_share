# 极简秒传 · HTTP Share

> 局域网文件极速共享工具 — 无需安装，双击即用

[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-nd/4.0/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d4.svg)]()

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📤 **一键分享** | 选择文件或文件夹，立即生成局域网访问链接 |
| 🌐 **智能网卡选择** | 自动优先选择能联通路由器/网关的网卡，无需手动配置 |
| 👥 **多人同时访问** | 基于多线程 HTTP Server，支持多设备并发下载 |
| 🔒 **IP 白名单** | 可开启访问控制，只允许指定 IP 访问 |
| 📥 **远程文件浏览** | 内置下载 Tab，可浏览并下载 HTTP / UNC 共享目录 |
| 👁 **在线文本预览** | 支持 30+ 文本格式（.py / .md / .json / .log 等）直接预览 |
| 📋 **访问日志** | 实时显示每一条连接记录，IP + 请求路径一目了然 |

---

## 🖥️ 界面预览

```
┌─────────────────────────────────────────┐
│  📤 分享          📥 下载               │
├─────────────────────────────────────────┤
│        快速共享文件                      │
│  [📄 选择文件]  [📁 选择文件夹]          │
│  ┌─────────────────────────────────┐    │
│  │  文件: example.zip              │    │
│  └─────────────────────────────────┘    │
│  ⚙ 展开设置                             │
│  共享链接:  http://192.168.1.5:8080/... │
│  [📋 复制链接]  [🌐 浏览器打开]          │
│  访问日志:                              │
│  [10:23:01] 192.168.1.8 - GET /... 200 │
└─────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 方式一：直接运行 EXE（推荐，无需 Python）

1. 前往 [Releases](../../releases) 页面下载最新版 `极简分享_vX.X.X.exe`
2. 双击运行，无需安装任何依赖

### 方式二：源码运行

**环境要求：** Python 3.10+

```bash
# 克隆项目
git clone https://github.com/huangyu6572/http_share.git
cd http_share

# 安装依赖
pip install psutil

# 运行
python main.py
```

### 方式三：自行打包

```bash
pip install pyinstaller psutil
python build.py
# 生成的 EXE 在 dist/ 目录下
```

---

## 📖 使用说明

### 分享文件 / 文件夹

1. 点击 **「📄 选择文件」** 或 **「📁 选择文件夹」**
2. HTTP 服务器自动启动，生成局域网链接
3. 将链接发送给同局域网的设备，对方浏览器即可直接下载

### 网卡选择

- 软件启动时**自动选择**能联通路由器/网关的网卡
- 点击 **「⚙ 展开设置」** 可手动切换网卡

### 开启访问白名单

1. 展开设置面板
2. 勾选 **「🔒 开启白名单」**
3. 输入允许访问的 IP 地址并点击「添加」

### 下载远程文件

1. 切换到 **「📥 下载」** Tab
2. 输入对方的共享链接（支持 `http://` 和 `\\server\share` UNC 路径）
3. 浏览目录，双击进入文件夹，右键或点击按钮下载

---

## 🛠️ 项目结构

```
http_share/
├── main.py          # 主程序（GUI + HTTP Server）
├── version.py       # 版本号管理
├── build.py         # 自动打包脚本（版本号自增）
├── test_main.py     # 单元测试（43 个测试用例）
└── README.md        # 本文件
```

---

## 🧪 运行测试

```bash
python -m pytest test_main.py -v
```

---

## 📦 版本历史

| 版本 | 主要更新 |
|------|---------|
| v1.0.5 | 智能网卡自动选择，优先选择能联通网关的网卡 |
| v1.0.4 | 可折叠设置面板，NIC 网卡选择器，Tab 样式优化 |
| v1.0.3 | 支持 file:// 和 UNC 路径访问 |
| v1.0.2 | 新增下载 Tab，支持远程文件浏览与文本预览 |
| v1.0.1 | 多线程支持，访问日志，IP 白名单 |
| v1.0.0 | 初始版本，文件/文件夹分享 |

---

## ⚖️ 许可证

Copyright © 2026 huangyu6572

本项目采用 **[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/deed.zh)** 许可证。

**您可以：**
- ✅ 查看、学习和研究本项目的源代码
- ✅ 在注明出处的前提下分享本项目链接

**您不可以：**
- ❌ 将本项目用于任何商业目的（包括但不限于销售、商业服务、商业产品集成）
- ❌ 对本项目进行修改后再发布（演绎作品）
- ❌ 直接复制本项目代码用于其他项目（无论是否商用）

> **简而言之：本项目仅供个人学习与研究，禁止商业使用，禁止二次分发或修改后发布。**

---

## 🤝 联系

如有问题或建议，欢迎提 [Issue](../../issues)。

---

**署名**

本说明文件由 huangyu6572 创建与维护。

---

**MIT 许可证**

Copyright (c) 2026 huangyu6572

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.