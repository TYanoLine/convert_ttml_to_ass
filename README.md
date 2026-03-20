# convert_ttml

TTML 形式の字幕を ASS 形式に変換するツールです。ruby（ふりがな）、縦書き、斜体のレンダリングに対応しています。

## 要件 / Requirements

このツールは **Windows 専用** です。テキスト幅測定に Windows GDI を使用するため、Windows 環境でのみ動作します。  
This tool is **Windows-only** as it requires Windows GDI for text width measurement.

- Python 3.11+ 
- Windows OS

## 使い方 / Usage

### 基本的な使用法 / Basic Usage

```bash
# 基本形式（オフセット時刻を指定）
python convert_ttml.py input.ttml output.ass -o 0:00:00.00

# 短形式（オフセット時刻を省略）
python convert_ttml.py input.ttml output.ass
```

**引数の説明 / Arguments:**
- `input` - 入力 TTML ファイルのパス / Input TTML file path
- `output` - 出力 ASS ファイルのパス / Output ASS file path
- `-o, --offset` - 引く時間オフセット（`HH:MM:SS.mmm` 形式または秒数、デフォルト: `0:00:00.00`） / Time offset to subtract in `HH:MM:SS.mmm` format or seconds (default: `0:00:00.00`)

### 使用例 / Examples

```bash
# オフセット5秒で変換
python convert_ttml.py sample.ttml output.ass -o 0:00:05.00

# FFmpeg を使用した ASS ファイルの適用
ffmpeg -i input.mp4 -vf ass=output.ass output.mp4
```

## 機能 / Features

### Ruby（ふりがな）レンダリング
- TTML の style 定義から ruby コンテナ、base 文字、ruby 文字を自動検出
- Ruby は base 文字の幅を実測し、その上に中央揃えで配置

### 縦書きサポート
- Region が `縦右` の段落は右から左へ、上から下へ描画
- 約物（括弧、ドット等）は縦書き用字形に自動変換
- 一部記号（ハイフン等）は 90 度回転
- 縦中横（`tts:textCombine="all"`）対応

### 文体対応
- TTML の `tts:fontStyle` から斜体を検出
- `tts:fontShear` でシアー（斜体的な効果）をサポート

## ASS 出力仕様 / ASS Output Specification

- 解像度 / Resolution: 1280×720
- 基本フォントサイズ / Base font size: 54
- Ruby フォントサイズ / Ruby font size: 26
- フォント / Font: BIZ UDPothic
- 2つのスタイルを使用：
  - `Default` - 横書き用
  - `Vertical` - 縦書き用（右詰め、斜体対応）

## ライセンス / License

MIT License - See [LICENSE](./LICENSE) for details.

Copyright (c) 2026 TYanoLine