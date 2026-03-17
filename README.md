# convert_ttml

TTML 形式の字幕を ASS 形式に変換するツールです。ruby（ふりがな）、縦書き、斜体のレンダリングに対応しています。

## 特徴（設計上の工夫点）

このスクリプトは TTML を単純に文字列置換するのではなく、**TTML の構造（p / br / style / region）を解析して、ASS の制御タグ（\pos, \an, \fs, \frz, \fax など）で再レンダリング**する方針になっています。特に日本語字幕で問題になりやすい「ルビ」「縦書き」「縦中横」「斜体（fontShear含む）」を崩れにくく出力するための処理が入っています。

- **TTML → パーツ列への平坦化**
  - `get_all_parts()` で `p` 要素配下を走査し、`text` / `br` / `ruby(base,ruby)` の並びに正規化します。
  - その後 `split_lines()` で `br` を境に行（横書き）/列（縦書き）として扱える形に分割します。

- **ルビ（横書き）の絶対配置レンダリング**
  - ルビを ASS の1行で表現しづらいため、`render_positioned_ruby_dialogues()` では
    1) ベース文字列を中央寄せで描画（`\an2\pos(...)`）
    2) ルビ文字を別レイヤーの Dialogue として上に重ねる（`\an8\pos(...)\s`）
    という2段構えで出力します。
  - ルビの X 座標は、ベース文字列の実際の描画幅を測って「対象文字列の中心」に合うように決めています。

- **縦書きの1文字単位レンダリング（記号補正・回転対応）**
  - `region == "縦右"` のときは `render_positioned_vertical_dialogues()` により、**1文字ずつ `\pos()` で絶対配置**します。
  - 縦書き時に形が崩れやすい約物は `VERTICAL_CHAR_MAP` による字形差し替えを行い、
    長音符などは `\frz90` で回転させます。
  - 一部文字は見た目のズレを減らすため、文字種ごとのオフセット補正も適用します。

- **縦中横（Tate-chu-yoko）対応**
  - `tts:textCombine="all"` が付いた style を収集し、該当箇所は縦書き中でも横向きの塊として配置します。
  - 実装上は幅を縮める（`\fscx`）ことで縦中横らしい見た目に寄せています。

- **スタイル解決（italic / fontShear の継承）**
  - TTML の `style` 参照（親 style の継承）をたどって `fontStyle` / `fontShear` を解決し、
    ASS 側の `\i`（斜体）や `\fax`（shear）に反映します。
  - これにより「固定の style ID 前提」ではなく、TTML の指定内容に追従する形になります。

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