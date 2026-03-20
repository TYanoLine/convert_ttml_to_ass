# convert_ttml

TTML 形式の字幕を ASS 形式に変換するツールです。ruby（ふりがな）、縦書き、斜体のレンダリングに対応しています。

## 要件 / Requirements

このツールは **Windows 専用** です。  
This tool is **Windows-only**.

- Python 3.11+ 
- Windows OS（テキスト幅測定に GDI を使用 / Uses Windows GDI for text width measurement）

## 使い方 / Usage

### 基本的な使用法 / Basic Usage

```bash
# TTML ファイルを ASS に変換（オフセット指定）
python convert_ttml.py 0:00:00.00 input.ttml output.ass

# FFmpeg を使用した ASS ファイルの使用例
ffmpeg -i input.mp4 -vf ass=output.ass output.mp4
```

第1引数はオフセット時刻（`HH:MM:SS.mmm` 形式）です。  
The first argument is the time offset in `HH:MM:SS.mmm` format.

## ライセンス / License

MIT License - See [LICENSE](./LICENSE) for details.

Copyright (c) 2026 TYanoLine