"""
NCM 音频格式转换器 (GUI 图形界面版)
支持：
- 拖拽单文件 / 多文件 / 文件夹直接批量转换
- 点击按钮选择文件 / 文件夹
- 自动后台多线程处理，界面丝滑不卡顿
- 转换进度条与详细结果列表
- 一键打开输出文件夹
"""

import os
import sys
import glob
import ctypes
from ctypes import wintypes
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ----------------- 寻找转换核心 ncm main.exe -----------------
DEFAULT_EXE_SEARCH_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "ncm main.exe"),
    r"C:\Users\tsuki\Desktop\Soft\ncm main\ncm main.exe",
]

def find_ncm_exe():
    # 优先检查 PyInstaller 单文件打包解压目录
    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "ncm main.exe")
        if os.path.exists(bundled):
            return bundled

    for p in DEFAULT_EXE_SEARCH_PATHS:
        if os.path.exists(p):
            return p
    return None

# ----------------- Windows 原生拖拽 (Drag & Drop) Hook -----------------
def hook_windows_dropfiles(window, callback):
    """
    通过 Windows Win32 API 挂钩 WM_DROPFILES，无需任何额外第三方库即可支持拖拽
    """
    WM_DROPFILES = 0x0233
    GWL_WNDPROC = -4
    hwnd = window.winfo_id()

    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    is_64bit = sys.maxsize > 2**32
    LRESULT = ctypes.c_int64 if is_64bit else ctypes.c_int32
    WPARAM = ctypes.c_uint64 if is_64bit else ctypes.c_uint32
    LPARAM = ctypes.c_int64 if is_64bit else ctypes.c_int32
    HWND = wintypes.HWND
    UINT = wintypes.UINT

    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

    if is_64bit:
        GetWindowLongPtr = user32.GetWindowLongPtrW
        SetWindowLongPtr = user32.SetWindowLongPtrW
    else:
        GetWindowLongPtr = user32.GetWindowLongW
        SetWindowLongPtr = user32.SetWindowLongW

    GetWindowLongPtr.argtypes = [HWND, ctypes.c_int]
    GetWindowLongPtr.restype = ctypes.c_void_p

    SetWindowLongPtr.argtypes = [HWND, ctypes.c_int, WNDPROC]
    SetWindowLongPtr.restype = ctypes.c_void_p

    user32.CallWindowProcW.argtypes = [ctypes.c_void_p, HWND, UINT, WPARAM, LPARAM]
    user32.CallWindowProcW.restype = LRESULT

    shell32.DragAcceptFiles.argtypes = [HWND, wintypes.BOOL]
    shell32.DragFinish.argtypes = [WPARAM]
    shell32.DragQueryFileW.argtypes = [WPARAM, UINT, wintypes.LPWSTR, UINT]
    shell32.DragQueryFileW.restype = UINT

    old_proc = None

    def py_wnd_proc(h, msg, wp, lp):
        if msg == WM_DROPFILES:
            count = shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
            files = []
            buf = ctypes.create_unicode_buffer(1024)
            for i in range(count):
                shell32.DragQueryFileW(wp, i, buf, 1024)
                files.append(buf.value)
            shell32.DragFinish(wp)
            if files:
                window.after(0, lambda: callback(files))
            return 0
        return user32.CallWindowProcW(old_proc, h, msg, wp, lp)

    new_proc = WNDPROC(py_wnd_proc)
    old_proc = GetWindowLongPtr(hwnd, GWL_WNDPROC)
    shell32.DragAcceptFiles(hwnd, True)
    SetWindowLongPtr(hwnd, GWL_WNDPROC, new_proc)

    # 保持引用，防止 Python 垃圾回收导致崩溃
    window._dnd_keepalive = (new_proc, old_proc)


# ----------------- GUI 界面主程序 -----------------
class NcmConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NCM 音频格式转换器")
        self.root.geometry("740x580")
        self.root.minsize(680, 500)
        
        # 居中显示
        self.center_window(740, 580)

        # 核心转换工具路径
        self.exe_path = find_ncm_exe()

        # 任务队列与状态
        self.file_queue = queue.Queue()
        self.is_converting = False
        self.last_output_dir = None
        self.total_count = 0
        self.success_count = 0
        self.fail_count = 0

        # UI 样式配置
        self.setup_styles()
        self.build_ui()

        # 启动后挂钩 Windows 拖拽
        self.root.after(100, lambda: hook_windows_dropfiles(self.root, self.handle_dropped_items))

    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        # 颜色常量
        self.COLOR_BG = "#F8FAFC"
        self.COLOR_CARD = "#FFFFFF"
        self.COLOR_PRIMARY = "#E60026"     # 网易云经典红
        self.COLOR_PRIMARY_HOVER = "#CC0022"
        self.COLOR_TEXT_MAIN = "#1E293B"
        self.COLOR_TEXT_MUTED = "#64748B"
        self.COLOR_BORDER = "#E2E8F0"
        self.COLOR_DROPZONE = "#F1F5F9"
        self.COLOR_DROPZONE_ACTIVE = "#FEE2E2"

        self.root.configure(bg=self.COLOR_BG)

        # 按钮样式
        style.configure("Primary.TButton",
                        font=("Microsoft YaHei UI", 10, "bold"),
                        background=self.COLOR_PRIMARY,
                        foreground="#FFFFFF",
                        borderwidth=0,
                        focuscolor="none",
                        padding=(14, 8))
        style.map("Primary.TButton",
                  background=[("active", self.COLOR_PRIMARY_HOVER), ("disabled", "#CBD5E1")])

        style.configure("Secondary.TButton",
                        font=("Microsoft YaHei UI", 10),
                        background="#FFFFFF",
                        foreground=self.COLOR_TEXT_MAIN,
                        borderwidth=1,
                        relief="solid",
                        focuscolor="none",
                        padding=(12, 8))
        style.map("Secondary.TButton",
                  background=[("active", "#F1F5F9")])

        # 进度条样式
        style.configure("TProgressbar",
                        troughcolor="#E2E8F0",
                        background=self.COLOR_PRIMARY,
                        thickness=10)

        # 树形列表样式
        style.configure("Treeview",
                        font=("Microsoft YaHei UI", 9),
                        rowheight=26,
                        background="#FFFFFF",
                        fieldbackground="#FFFFFF",
                        foreground=self.COLOR_TEXT_MAIN)
        style.configure("Treeview.Heading",
                        font=("Microsoft YaHei UI", 9, "bold"),
                        background="#F1F5F9",
                        foreground=self.COLOR_TEXT_MAIN)
        style.map("Treeview", background=[("selected", "#EFF6FF")])

    def build_ui(self):
        # 顶部标题栏
        top_frame = tk.Frame(self.root, bg=self.COLOR_BG, padx=24, pady=16)
        top_frame.pack(fill="x")

        title_label = tk.Label(top_frame,
                               text="🎵 NCM 音频转换器",
                               font=("Microsoft YaHei UI", 16, "bold"),
                               fg=self.COLOR_TEXT_MAIN,
                               bg=self.COLOR_BG)
        title_label.pack(anchor="w")

        sub_label = tk.Label(top_frame,
                             text="将网易云音乐加密歌曲 (.ncm) 快速无损还原为 MP3 / FLAC 音频",
                             font=("Microsoft YaHei UI", 9),
                             fg=self.COLOR_TEXT_MUTED,
                             bg=self.COLOR_BG)
        sub_label.pack(anchor="w", pady=(2, 0))

        # 中部：拖拽卡片区 (兼做可点击区)
        self.drop_frame = tk.Frame(self.root,
                                   bg=self.COLOR_DROPZONE,
                                   highlightbackground=self.COLOR_BORDER,
                                   highlightthickness=2,
                                   padx=20,
                                   pady=24,
                                   cursor="hand2")
        self.drop_frame.pack(fill="x", padx=24, pady=4)
        self.drop_frame.bind("<Button-1>", lambda e: self.select_files())

        self.drop_icon = tk.Label(self.drop_frame,
                                  text="📥",
                                  font=("Segoe UI Emoji", 32),
                                  bg=self.COLOR_DROPZONE)
        self.drop_icon.pack()
        self.drop_icon.bind("<Button-1>", lambda e: self.select_files())

        self.drop_text1 = tk.Label(self.drop_frame,
                                   text="把 .ncm 文件或整个文件夹拖拽到此处",
                                   font=("Microsoft YaHei UI", 12, "bold"),
                                   fg=self.COLOR_TEXT_MAIN,
                                   bg=self.COLOR_DROPZONE)
        self.drop_text1.pack(pady=(6, 2))
        self.drop_text1.bind("<Button-1>", lambda e: self.select_files())

        self.drop_text2 = tk.Label(self.drop_frame,
                                   text="支持多文件批量拖入，或点击此处选择文件",
                                   font=("Microsoft YaHei UI", 9),
                                   fg=self.COLOR_TEXT_MUTED,
                                   bg=self.COLOR_DROPZONE)
        self.drop_text2.pack()
        self.drop_text2.bind("<Button-1>", lambda e: self.select_files())

        # 按钮控制栏
        btn_frame = tk.Frame(self.root, bg=self.COLOR_BG, padx=24, pady=12)
        btn_frame.pack(fill="x")

        btn_files = ttk.Button(btn_frame,
                               text="📂 选择 NCM 文件...",
                               style="Primary.TButton",
                               command=self.select_files)
        btn_files.pack(side="left", padx=(0, 10))

        btn_dir = ttk.Button(btn_frame,
                             text="📁 选择包含歌曲的文件夹...",
                             style="Secondary.TButton",
                             command=self.select_directory)
        btn_dir.pack(side="left", padx=(0, 10))

        self.btn_open_dir = ttk.Button(btn_frame,
                                       text="🔍 打开输出目录",
                                       style="Secondary.TButton",
                                       command=self.open_output_dir)
        self.btn_open_dir.pack(side="left", padx=(0, 10))

        btn_clear = ttk.Button(btn_frame,
                               text="清空列表",
                               style="Secondary.TButton",
                               command=self.clear_list)
        btn_clear.pack(side="right")

        # 进度条与状态显示
        progress_frame = tk.Frame(self.root, bg=self.COLOR_BG, padx=24, pady=4)
        progress_frame.pack(fill="x")

        self.progress_bar = ttk.Progressbar(progress_frame,
                                            style="TProgressbar",
                                            mode="determinate")
        self.progress_bar.pack(fill="x", pady=(0, 6))

        self.status_label = tk.Label(progress_frame,
                                     text="就绪：请拖入或选择 .ncm 文件开始转换",
                                     font=("Microsoft YaHei UI", 9),
                                     fg=self.COLOR_TEXT_MUTED,
                                     bg=self.COLOR_BG)
        self.status_label.pack(anchor="w")

        # 任务记录列表 (Treeview)
        list_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        list_frame.pack(fill="both", expand=True, padx=24, pady=(6, 16))

        columns = ("name", "status", "dir")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="音频文件名称")
        self.tree.heading("status", text="状态")
        self.tree.heading("dir", text="所在目录")

        self.tree.column("name", width=320, anchor="w")
        self.tree.column("status", width=100, anchor="center")
        self.tree.column("dir", width=260, anchor="w")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 检查后端引擎存在性
        self.check_engine()

    def check_engine(self):
        if not self.exe_path or not os.path.exists(self.exe_path):
            self.status_label.config(
                text="⚠️ 未找到 ncm main.exe 转换引擎！请点击下方指定路径",
                fg="#DC2626"
            )
            self.root.after(500, self.prompt_select_exe)

    def prompt_select_exe(self):
        msg = "未在默认路径检测到 'ncm main.exe'。\n是否立即手动指定其位置？"
        if messagebox.askyesno("提示", msg):
            chosen = filedialog.askopenfilename(
                title="选择 ncm main.exe",
                filetypes=[("可执行程序", "ncm main.exe"), ("EXE 文件", "*.exe")]
            )
            if chosen and os.path.exists(chosen):
                self.exe_path = chosen
                self.status_label.config(text="就绪：转换引擎已绑定", fg=self.COLOR_TEXT_MUTED)

    # ----------------- 用户操作响应 -----------------
    def select_files(self):
        files = filedialog.askopenfilenames(
            title="选择 NCM 格式音频文件",
            filetypes=[("网易云加密音乐", "*.ncm"), ("所有文件", "*.*")]
        )
        if files:
            self.add_paths_to_queue(files)

    def select_directory(self):
        folder = filedialog.askdirectory(title="选择包含 NCM 文件的文件夹")
        if folder:
            self.add_paths_to_queue([folder])

    def handle_dropped_items(self, items):
        if items:
            self.add_paths_to_queue(items)

    def add_paths_to_queue(self, paths):
        if not self.exe_path or not os.path.exists(self.exe_path):
            self.prompt_select_exe()
            if not self.exe_path or not os.path.exists(self.exe_path):
                return

        # 展开所有文件夹，提取所有 .ncm 文件
        found_files = []
        for p in paths:
            if os.path.isdir(p):
                # 递归遍历目录中的 .ncm
                for root_dir, _, filenames in os.walk(p):
                    for fn in filenames:
                        if fn.lower().endswith(".ncm"):
                            found_files.append(os.path.join(root_dir, fn))
            elif os.path.isfile(p):
                if p.lower().endswith(".ncm"):
                    found_files.append(p)
                else:
                    # 如果用户拖入了没有扩展名但实际是文件的
                    found_files.append(p)

        if not found_files:
            messagebox.showinfo("提示", "未在选择的内容中找到 .ncm 格式文件！")
            return

        # 加入表格与队列
        for f in found_files:
            fn = os.path.basename(f)
            fd = os.path.dirname(f)
            item_id = self.tree.insert("", "end", values=(fn, "⏳ 等待中", fd))
            self.file_queue.put((item_id, f))

        self.total_count += len(found_files)
        self.progress_bar["maximum"] = self.total_count
        self.progress_bar["value"] = self.success_count + self.fail_count

        if not self.is_converting:
            self.start_conversion_thread()

    def start_conversion_thread(self):
        self.is_converting = True
        t = threading.Thread(target=self.process_queue_worker, daemon=True)
        t.start()

    def process_queue_worker(self):
        while not self.file_queue.empty():
            item_id, filepath = self.file_queue.get()
            dirname = os.path.dirname(filepath)
            filename = os.path.basename(filepath)

            # 更新 UI 状态为转换中
            self.root.after(0, self.update_item_status, item_id, "🔄 转换中...")
            self.root.after(0, self.update_status_text, f"正在转换：{filename}")

            success = self.convert_single_file(filepath)

            if success:
                self.success_count += 1
                self.last_output_dir = dirname
                self.root.after(0, self.update_item_status, item_id, "✅ 完成")
            else:
                self.fail_count += 1
                self.root.after(0, self.update_item_status, item_id, "❌ 失败")

            current_progress = self.success_count + self.fail_count
            self.root.after(0, self.update_progress, current_progress)
            self.file_queue.task_done()

        self.is_converting = False
        summary = f"转换完成！成功 {self.success_count} 首"
        if self.fail_count > 0:
            summary += f"，失败 {self.fail_count} 首"
        self.root.after(0, self.update_status_text, summary)

    def convert_single_file(self, filepath):
        try:
            # 执行 ncm main.exe
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [self.exe_path, filepath],
                capture_output=True,
                creationflags=creationflags,
                text=True
            )
            
            # 校验是否成功生成了同名 .mp3 或 .flac
            base_without_ext = os.path.splitext(filepath)[0]
            possible_outputs = [
                base_without_ext + ".mp3",
                base_without_ext + ".flac",
            ]
            for out in possible_outputs:
                if os.path.exists(out):
                    return True

            # 如果没有同名文件，通过返回码判断
            return result.returncode == 0
        except Exception as e:
            print("转换出错:", e)
            return False

    def update_item_status(self, item_id, status_str):
        cur_vals = self.tree.item(item_id, "values")
        if cur_vals:
            self.tree.item(item_id, values=(cur_vals[0], status_str, cur_vals[2]))
            self.tree.see(item_id)

    def update_status_text(self, text):
        self.status_label.config(text=text, fg=self.COLOR_TEXT_MAIN)

    def update_progress(self, val):
        self.progress_bar["value"] = val

    def clear_list(self):
        if self.is_converting:
            messagebox.showwarning("提示", "正在转换中，请稍候再清空！")
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.total_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.progress_bar["value"] = 0
        self.status_label.config(text="就绪：请拖入或选择 .ncm 文件开始转换", fg=self.COLOR_TEXT_MUTED)

    def open_output_dir(self):
        target_dir = self.last_output_dir
        # 如果还没转换过，尝试取表格第一项的目录
        if not target_dir:
            children = self.tree.get_children()
            if children:
                target_dir = self.tree.item(children[0], "values")[2]

        if target_dir and os.path.exists(target_dir):
            os.startfile(target_dir)
        else:
            messagebox.showinfo("提示", "尚未有转换完成的文件目录！")


if __name__ == "__main__":
    root = tk.Tk()
    app = NcmConverterApp(root)
    root.mainloop()
