"""Bilibili audio/video downloader with a small desktop interface."""
import os
import json
import queue
import re
import shutil
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BASE = Path(__file__).resolve().parent


def normalize_input(value):
    value = value.strip()
    match = re.fullmatch(r"BV[0-9A-Za-z]{10}", value, re.I)
    page = "1"
    if not match:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or parsed.hostname not in ("www.bilibili.com", "bilibili.com", "m.bilibili.com"):
            raise ValueError("请输入完整 BV 号或 bilibili.com/video/BV… 视频链接。")
        match = re.fullmatch(r"/video/(BV[0-9A-Za-z]{10})/?", parsed.path, re.I)
        if not match:
            raise ValueError("链接中没有有效的 BV 号。")
        page = parse_qs(parsed.query).get("p", ["1"])[0]
        if not page.isdecimal() or int(page) < 1:
            raise ValueError("分 P 编号必须是正整数。")
        bv = match.group(1)
    else:
        bv = match.group(0)
    return f"https://www.bilibili.com/video/BV{bv[2:]}?p={int(page)}"


def validate_free_metadata(payload):
    if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        raise ValueError("无法确认视频免费状态，已停止下载。")
    data = payload["data"]
    rights = data.get("rights")
    if not isinstance(rights, dict) or "pay" not in rights:
        raise ValueError("缺少付费状态信息，已停止下载。")
    for key in ("pay", "ugc_pay", "ugc_pay_preview", "is_upower_exclusive", "is_upower_pay", "arc_pay"):
        if rights.get(key, 0) not in (0, False, None) or data.get(key, 0) not in (0, False, None):
            raise ValueError("此视频含付费、充电专属或付费试看标记，仅支持免费视频。")
    if data.get("is_chargeable_season") or data.get("redirect_url"):
        raise ValueError("不支持收费合集或跳转到番剧等页面的视频。")
    return data


def check_free(url):
    bv = urlparse(url).path.split("/")[-1]
    request = Request(f"https://api.bilibili.com/x/web-interface/view?bvid={bv}", headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/",
    })
    # A fresh urllib request sends no browser cookies or account credentials.
    with urlopen(request, timeout=30) as response:
        data = validate_free_metadata(json.load(response))
    page = int(parse_qs(urlparse(url).query)["p"][0])
    if not any(item.get("page") == page for item in data.get("pages", [])):
        raise ValueError("指定的分 P 不存在，已停止下载。")


def build_options(folder, mode, ffmpeg):
    options = {
        "format": "bestaudio" if mode == "audio" else "bestvideo+bestaudio/best",
        "outtmpl": str(Path(folder) / mode / "%(title).150B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "windowsfilenames": True,
        "ffmpeg_location": ffmpeg,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "continuedl": True,
    }
    if mode == "audio":
        options["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    else:
        options["merge_output_format"] = "mkv"
    return options


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        root.title("B站音频 / 视频下载")
        root.geometry("720x520")
        root.minsize(620, 460)
        panel = ttk.Frame(root, padding=20)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="B站下载", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(panel, text="输入 BV 号或视频链接，默认仅下载 MP3 音频。").pack(anchor="w", pady=(6, 12))
        self.source = tk.StringVar()
        ttk.Entry(panel, textvariable=self.source).pack(fill="x")
        modes = ttk.Frame(panel)
        modes.pack(fill="x", pady=12)
        self.mode = tk.StringVar(value="audio")
        ttk.Radiobutton(modes, text="仅音频（MP3）", variable=self.mode, value="audio").pack(side="left")
        ttk.Radiobutton(modes, text="视频（含声音）", variable=self.mode, value="video").pack(side="left", padx=20)
        self.folder = tk.StringVar(value=str(BASE / "downloads"))
        self.path_row(panel, "保存位置", self.folder, self.choose_folder)
        ttk.Label(panel, text="仅支持匿名可观看的免费视频；不提供账号登录或付费试看下载。").pack(anchor="w", pady=4)
        ttk.Label(panel, text="默认下载第 1 P；下载其他分 P 请粘贴带 ?p=2 等参数的链接。").pack(anchor="w", pady=8)
        row = ttk.Frame(panel)
        row.pack(fill="x", pady=(0, 10))
        self.button = ttk.Button(row, text="开始下载", command=self.start)
        self.button.pack(side="left")
        ttk.Button(row, text="打开保存目录", command=self.open_folder).pack(side="left", padx=10)
        self.status = tk.StringVar(value="等待输入 BV 号")
        ttk.Label(panel, textvariable=self.status).pack(anchor="w")
        self.progress = ttk.Progressbar(panel, maximum=100)
        self.progress.pack(fill="x", pady=8)
        self.log = tk.Text(panel, height=10, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def path_row(self, parent, label, variable, command):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=17).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择", command=command).pack(side="left", padx=(8, 0))

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder.set(path)

    def open_folder(self):
        try:
            path = Path(self.folder.get()).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("无法打开目录", str(exc))

    def start(self):
        if self.busy:
            return
        try:
            url = normalize_input(self.source.get())
            if not self.folder.get().strip():
                raise ValueError("请选择保存目录。")
            folder = Path(self.folder.get()).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as exc:
            messagebox.showerror("输入有误", str(exc))
            return
        self.busy = True
        self.button.configure(state="disabled")
        self.progress["value"] = 0
        self.status.set("正在获取视频信息…")
        threading.Thread(target=self.download, args=(url, str(folder), self.mode.get()), daemon=True).start()

    def download(self, url, folder, mode):
        try:
            import yt_dlp
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("未找到 FFmpeg。请安装 FFmpeg 并加入 PATH，重新打开程序。")
            self.events.put(("status", "正在检查视频免费状态…"))
            check_free(url)
            options = build_options(folder, mode, ffmpeg)
            events = self.events

            class Logger:
                def debug(self, message):
                    if not message.startswith("[debug]"):
                        events.put(("log", message))

                def warning(self, message):
                    events.put(("log", "提示：" + message))

                def error(self, message):
                    events.put(("log", message))

            def progress(data):
                if data["status"] == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate")
                    downloaded = data.get("downloaded_bytes", 0)
                    percent = min(100, downloaded / total * 100) if total else 0
                    events.put(("progress", (percent, f"下载中：{percent:.1f}%" if total else f"已下载 {downloaded / 1048576:.1f} MB")))
                elif data["status"] == "finished":
                    events.put(("status", "下载完成，正在转换音频 / 合并视频…"))

            options.update(logger=Logger(), progress_hooks=[progress])
            with yt_dlp.YoutubeDL(options) as downloader:
                result = downloader.download([url])
            if result:
                raise RuntimeError("下载未成功，请查看日志。")
            events.put(("done", str(Path(folder) / mode)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def poll(self):
        for _ in range(200):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                self.progress["value"], status = value
                self.status.set(status)
            elif kind == "status":
                self.status.set(value)
            else:
                self.log.configure(state="normal")
                self.log.insert("end", value + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
                if kind in ("done", "error"):
                    self.busy = False
                    self.button.configure(state="normal")
                    self.status.set("下载完成：" + value if kind == "done" else "下载失败，详见日志")
                    if kind == "done":
                        self.progress["value"] = 100
        self.root.after(100, self.poll)

    def close(self):
        if self.busy and not messagebox.askyesno("正在下载", "退出会中断当前下载，确定退出？"):
            return
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
