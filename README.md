# LuminaRouteFinder

Lumina’s Corridorのスクリーンショットから、第1段階→第10段階の最大通過アイコン数と経路を求めるPythonスクリプトです。横移動は双方向、上移動・同じアイコンの再訪・線の交差点での乗り換えは禁止します。起点・終点を数え、第1・第10段階でも横移動できます。

## Windows版ダウンロード（Python不要）

**[LuminaRouteFinder.exe をダウンロード](https://github.com/T0m-n0-k4ti-desu/LuminaRouteFinder/releases/latest/download/LuminaRouteFinder.exe)**

[リリース一覧](https://github.com/T0m-n0-k4ti-desu/LuminaRouteFinder/releases) · [SHA-256チェックサム](https://github.com/T0m-n0-k4ti-desu/LuminaRouteFinder/releases/latest/download/SHA256SUMS.txt)

Windows 10 / 11 の64ビット向けです。exeを任意の書き込み可能なフォルダーに保存し、ダブルクリックして起動してください。Pythonや追加ライブラリのインストールは不要です。画像を選択またはD&Dし、「解析」を押すと結果を表示します。

結果はexeと同じフォルダーの `outputs/gui/` に保存します。初回起動は同梱ファイルの展開に少し時間がかかる場合があります。この配布物はコード署名を付けていません。

## 入力画像と解析結果の例

ゲーム内で回廊ミッションのウィンドウを開き、タイトルバーと全10段階、接続線が見える状態で撮影します。下の段の選択を解除し、カーソルを盤面外に移動してください。背景を含むスクリーンショットをそのまま指定できます。

![入力例：全10段階の盤面と接続線が見えるゲーム画面](docs/images/sample_image.jpg)

このサンプルはリポジトリに同梱しています。GUIにドロップするか、次のように画像を指定して起動できます。起動後に「解析」を押してください。

```powershell
python -m lumina_route_finder.gui docs\images\sample_image.jpg
```

解析後は、左側に番号付きの経路画像、右側に最大通過数と通過順を表示します。以下は最大14アイコン・同率8通りの表示例です。画像下の「前へ／次へ」で別の候補に切り替え、「全体表示」「＋」「－」で表示倍率を調整できます。

![GUIの解析結果例：最大14アイコン、同率8通りの候補をページ切り替え](docs/images/pyw_image.jpg)

## セットアップ

Python 3.10以降を使用してください。リポジトリのルート（`DESIGN.md` とこのファイルがある場所）で実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

すでにOpenCV・NumPyが利用できるPythonなら、その環境でも実行できます。外部APIやOCR実行ファイルは使いません。

## GUIで使う

依存ライブラリを更新して起動します。

```powershell
python -m pip install -r requirements.txt
python -m lumina_route_finder.gui
```

Windowsでは `launch_gui.pyw` のダブルクリックでも起動できます。Pythonとのファイル関連付け・依存ライブラリの準備が必要です。

1. 画像パスを入力するか、「画像を選択…」から選びます。パス欄・ドロップ領域・画像表示領域へのD&Dでも指定できます。
2. 「解析」を押します。解析中はボタンを無効化し、進行表示を出します。ドロップ領域の下のバーは処理中の表示で、待機中・完了後は非表示になります。
3. 成功時は最大通過数と経路画像、通過順を表示します。画像は全体表示・拡大縮小・スクロールで確認できます。
4. エラー時は日本語の理由と対応方法、エラー箇所を示す画像に切り替わります。盤面を検出できない場合は入力画像、画像自体を読み込めない場合は理由のみ表示します。

画像を変更すると前の結果を画面から消します。入力は1枚ずつです。同率最長経路がある場合は、画像下の「前へ／次へ」で候補を切り替えられます。「候補 n／総数」と通過順も更新します。最初に20件まで取得し、さらに次へ進むと候補を追加取得します。追加取得中も進行表示を出します。

結果は実行フォルダー内の `outputs/gui/` の下に実行ごとの新しいフォルダーとして保存します。「結果フォルダーを開く」から参照できます。既存の出力を上書きしません。ダブルクリック起動ではリポジトリ内が保存先です。

```powershell
# 起動時に画像を指定（解析はボタンで開始）
python -m lumina_route_finder.gui docs\images\sample_image.jpg

# 保存先の変更
python -m lumina_route_finder.gui --output-dir D:\LuminaResults
```

GUIはPython付属のTkinterと、ファイルD&D用の [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) を使用します。解析は別スレッドで実行します。認識できる画面条件はCLIと同じです。

## 実行

現在のフォルダー構成では、画像フォルダーはリポジトリの1階層上にあります。

```powershell
# 1枚
python -m lumina_route_finder ..\sample_image\TWCI_2026_11_1_1_2_47.jpg

# フォルダーを再帰処理
python -m lumina_route_finder ..\sample_image --output-dir outputs\samples

# エラー画像の検査（拒否するため終了コードは1）
python -m lumina_route_finder ..\error_images --output-dir outputs\errors
```

入力画像ごとに `outputs/<入力ファイル名>/` を作ります。同じ出力先が存在する場合は `.1`、`.2` のように新しいフォルダーを作り、前の結果を上書きしません。

| 出力 | 内容 |
|---|---|
| `result.json` | 成否、最大通過数、経路、同率最長経路数、またはエラー理由 |
| `route.png` | 代表経路の矢印と通過順を重ねた盤面画像 |
| `recognized.png` | 認識したすべての接続を赤線で示した確認画像 |
| `board.json` | 認識したマス・接続・辺ごとの判定指標 |
| `board.png` | 経路を描く前の盤面（GUIの候補切り替えに使用） |
| `error.png` | 検出できた盤面にエラー箇所を示した画像 |

JSON内のマス位置は `[段階, 列]` の1始まりです。同率経路は標準で最大20件まで保存します。`--max-paths 100` で変更できます。同率最長経路の総数は出力上限に関係なく計算します。

終了コードは、全件正常なら0、認識エラーまたは到達不能があれば1、CLI引数不正なら2です。エラー時には最大通過数を出力しません。正しく読めたグラフでゴールに到達できない場合は `no_path` として区別します。

## 撮影条件と対応範囲

- 提供画像と同じUI倍率（1x）に対応しています。画面全体の解像度やウィンドウ位置は固定しません。
- タイトルバーと10段階すべてが写るように撮影してください。
- 下部のアイコン選択を解除し、上部を含むすべての接続が見える状態にしてください。
- ゲーム内カーソルは盤面外に移動してください。右側の説明欄に置いても構いません。
- ウィンドウ外の背景や右側の説明・キャラクター欄は経路認識に使いません。

タイトルバーからUI倍率（基準の0.5～3倍）と位置を自動検出し、背景から盤面を切り出して260×500ピクセルに正規化してから解析します。ゲーム背景やウィンドウ位置に依存しません。全10段階とタイトルバーを含めて撮影してください。倍率範囲内でも、縮小で接続線が失われた画像、縦横比を変えた画像、別レイアウト・別形状のカーソル、遮蔽や強い画像劣化は認識できない場合があります。出力の盤面画像・エラー枠は正規化後の座標、`board_origin` は元画像の座標です。

接続認識は点線の局所コントラストを使い、判定を確定できない場合は `AMBIGUOUS_CONNECTION` で停止します。認識が確実な正常画像を基準に使用し、初めて扱う撮影条件では `recognized.png` を確認してください。

## 手動グラフの探索

画像認識から独立して探索処理を利用できます。JSONは `board.json` と同じ `nodes`・`edges` 形式です。横辺は1回だけ書けば双方向になり、段間の辺は上から下に書きます。

```powershell
python -m lumina_route_finder examples\small_board.json --graph --output-dir outputs\graph
```

この例は3段×2列の小さな盤面で、6アイコンを通過します。画像入力の盤面は10段×5列固定です。

## 検証

```powershell
python -m unittest discover -s tests -v
```

画像テストは標準でリポジトリの1階層上の `sample_image`・`error_images` を参照します。別の場所では `LUMINA_SAMPLE_ROOT` に、その2フォルダーを含む親フォルダーを指定してください。画像がない環境では画像テストをスキップします。

```powershell
$env:LUMINA_SAMPLE_ROOT = 'D:\path\to\images'
python -m unittest discover -s tests -v
```

確認した内容:

- 正常例14枚すべてで第10段階までの経路を検出。
- エラー例5枚を、下部選択3枚・カーソル遮蔽2枚として拒否。
- 最初の正常例について、目視照合した接続の正解データと一致（最大16アイコン）。他13枚の全辺の独立した正解データは未作成。
- 盤面とヘッダー以外をランダムノイズに差し替えても接続が一致。
- ウィンドウの平行移動後も接続が一致。
- カーソルの一部が盤面外に出る場合、アイコン欠損、切れた画像、複数ウィンドウを拒否。
- 小規模ランダムグラフ100件で、独立した全経路列挙と最大値・同率経路が一致。

認識テンプレートの元となる検証画像群はGitに含めず、切り出した小さなPNGを同梱しています。README用の入力サンプルとGUI画面は `docs/images/` に格納しています。再生成する場合:

```powershell
python tools\build_templates.py ..
```

設計の詳細は [DESIGN.md](DESIGN.md) を参照してください。

GUIのテストでは、空白・日本語を含むD&Dパス、非同期解析、成功後のエラー遷移、読み込めない画像、想定外エラーからの操作復帰を確認します。画面表示を利用できない環境ではTkウィジェットのテストをスキップします。

## 配布用exeをビルドする

Windows上で、リポジトリのルートから実行します。ビルド用の依存バージョンは `requirements-build.txt` に固定しています。

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe tools\build_exe.py
```

`dist/LuminaRouteFinder.exe` と `dist/SHA256SUMS.txt` を生成します。ビルド後はexe自体を起動し、GUI・TkDnD・同梱テンプレート・サンプル解析・画像表示を自動確認します。認識用アセットと必要なライブラリをexeに含め、実行時の一時展開先には結果を保存しません。

配布ファイルはGitのソース履歴に入れず、GitHub Releasesの添付ファイルとして公開します。READMEのダウンロードリンクは最新リリースの `LuminaRouteFinder.exe` を参照します。
