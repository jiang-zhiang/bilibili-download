# B站音频 / 视频下载

 ![image-20260910121120165](C:\Users\zhi-ang\AppData\Roaming\Typora\typora-user-images\image-20260910121120165.png)

双击 `start.bat` 启动。首次启动会自动建立本地 Python 虚拟环境并安装 yt-dlp，需要联网。

1. 输入 BV 号，例如 `BV1xx411c7mD`，或粘贴完整视频链接。
2. 默认选中「仅音频（MP3）」。需要带声音的视频时选择「视频（含声音）」。
3. 点击「开始下载」。文件保存在程序目录的 `downloads/audio` 或 `downloads/video` 中，也可以自己选择位置。

音频为 192 kbps MP3（转码不会提高源音质）。视频选择匿名可获取的最佳画质，合并为 MKV；若源文件已包含音视频，可能保留源容器格式。默认仅下载第 1 P，其他分 P 使用带 `?p=2` 等参数的完整链接。

## 运行环境

- Windows，Python 3.10 或以上（包含 tkinter）。
- FFmpeg 加入 PATH。本机已检测到 Python 3.12 和 FFmpeg。
- 下载引擎：[yt-dlp 官方项目](https://github.com/yt-dlp/yt-dlp)。

## 仅限免费视频

程序不读取浏览器 Cookies，不提供账号登录。下载前通过视频信息接口检查付费、充电专属、付费试看等标记；收费合集和跳转视频也会拒绝。接口失败或缺少必要状态字段时停止下载，不尝试绕过。仅选择匿名可获取的音视频流，会员画质不可用。判断依赖 B 站返回的元数据；若站点接口变化，需要更新检查逻辑。

## 常见错误

网络错误或 403 / 412 可稍后重试；若网站更新导致解析失败，在程序目录运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -U yt-dlp
```

关闭窗口会中断当前任务；保留的临时文件可供下次尝试续传。请只下载你有权保存的内容。

## 源码与 GitHub

`bilibili_downloader.py` 为完整程序源码，`start.bat` 为启动脚本，`requirements.txt` 为依赖清单。`.gitignore` 已排除虚拟环境、下载文件和常见 Cookies 文件。后续可将源代码、测试和说明上传 GitHub；不需要上传 `.venv` 或下载的视频音频。

运行测试：`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
