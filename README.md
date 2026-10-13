# 🎵 NCM 音频格式转换器 (NCM Audio Converter GUI)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-green.svg)](https://www.microsoft.com/windows/)
[![License](https://img.shields.io/badge/License-MIT-orange.svg)](LICENSE)

一个极简、现代化且高效的网易云音乐加密音频格式 (`.ncm`) 解密转换工具，提供友好的图形用户界面（GUI），支持拖拽批量转换并完整还原 ID3 标签信息（歌名、歌手、专辑、封面等）。

---

## ✨ 核心特性

- 📥 **双模交互，极致易用**：
  - **拖拽转换**：支持将单个文件、多个文件或整个音乐文件夹直接拖入窗口。
  - **按钮选择**：支持一键选择单曲或选择整个歌曲目录进行批量扫描。
- ⚡ **无假死多线程架构**：采用后台工作线程异步处理转换任务，处理海量音乐时界面依然丝滑流畅，绝不卡死。
- 📊 **可视化进度与清单**：清晰展示排队状态（⏳ 等待中、🔄 转换中、✅ 已完成、❌ 失败）与整体进度条。
- 🏷️ **完整元数据还原**：自动提取内嵌的高清封面图片、歌曲名、艺术家名、专辑等 ID3 标签信息写入输出的 MP3 / FLAC 文件中。
- 🔍 **一键直达**：转换完成后可一键在文件资源管理器中打开目标音频所在目录。
- 📦 **零第三方依赖**：源码仅基于 Python 原生库与 Windows Win32 API（ctypes），克隆即跑，无需繁杂的依赖安装。

---

## 🖥️ 界面预览

- 拖拽区域支持大面积释放，点击亦可唤起文件选择对话框。
- 底部表格实时呈现每首歌曲的转换状态与所在目录。

---

## 🚀 快速上手

### 方式一：直接运行源码

确保电脑已安装 Python 3.8 或更高版本：

```bash
# 启动图形界面 (无控制台黑框)
pythonw app.py
```

或双击目录下的 `启动转换器.bat`。

---

### 方式二：打包为独立单文件 `.exe`

如果你希望将工具打包为一个无需 Python 环境即可独立分发的单文件可执行程序，可以使用 PyInstaller：

```bash
# 安装 pyinstaller
pip install pyinstaller

# 一键打包
pyinstaller --noconfirm --onefile --windowed --add-binary "ncm main.exe;." --name "NCM音乐格式转换器" app.py
```

打包完成后，独立的可执行文件将位于 `dist/NCM音乐格式转换器.exe`。

---

## 🛠️ 技术原理

1. **加解密算法**：基于网易云音乐 `.ncm` 格式逆向分析，提取 AES-128-ECB 密钥并结合变种 RC4 密钥箱还原原始音频流（MP3/FLAC）。
2. **Windows 原生拖拽**：使用 Python `ctypes` 挂钩 Windows `WM_DROPFILES` 消息机制与 `DragQueryFileW`，支持完整 Unicode/中文路径拖拽。
3. **核心转换引擎**：集成高性能底层处理引擎 `ncmdump`。

---

## 📄 免责声明 (Disclaimer)

- 本工具仅供编程学习、技术交流以及个人合法购买/缓存的音频文件格式转换使用。
- 请勿将本工具用于任何商业用途或侵犯版权的行为。版权归各音乐创作者及版权所有方所有。

---

## 📜 开源协议

本项目采用 [MIT 许可证](LICENSE)。
底层解码算法致敬开源项目 [ncmdump](https://github.com/anonymous5l/ncmdump)。
