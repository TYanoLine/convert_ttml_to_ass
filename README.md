# convert_ttml

TTML 形式の字幕を ASS 形式に変換するツールです。ルビ（ふりがな）、縦書き、斜体のレンダリングに対応しています。

## 要件 / Requirements

このツールは **Windows 専用** です。  
This tool is **Windows-only**.

- Python 3.11+ 
- Windows OS（テキスト幅測定に GDI を使用 / Uses Windows GDI for text width measurement）

## 使い方 / Usage

### 基本的な使用法 / Basic Usage

# TTML ファイルを ASS に変換
python convert_ttml.py input.ttml output.ass

# オフセットを指定して変換（開始時間を 5 秒早める）
python convert_ttml.py input.ttml output.ass --offset 0:00:05.00

# ヘルプを表示
python convert_ttml.py --help
```

### FFmpeg での使用例

```bash
ffmpeg -i input.mp4 -vf ass=output.ass output.mp4
```

## 引数 / Arguments

- `input`: 入力する TTML ファイルのパス。
- `output`: 出力する ASS ファイルのパス。
- `-o, --offset`: オフセット時刻（`HH:MM:SS.mmm` 形式または秒数）。指定した時間分だけ字幕の開始・終了時間が前倒しされます（デフォルト: 0:00:00.00）。

## ライセンス / License

MIT License - See [LICENSE](./LICENSE) for details.

Copyright (c) 2026 TYanoLine
