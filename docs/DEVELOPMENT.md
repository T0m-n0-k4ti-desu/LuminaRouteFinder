# Python実行・開発・リリース手順

[READMEへ戻る](../README.md)

## セットアップとGUI起動

Python 3.10以降を使用し、リポジトリ直下で実行します。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m lumina_route_finder.gui
```

Windowsでは `launch_gui.pyw` のダブルクリックでも起動できます。Pythonとのファイル関連付けと依存ライブラリが必要です。

```powershell
# 画像を指定して起動（解析はボタンで開始）
python -m lumina_route_finder.gui docs\images\sample_image.jpg

# 出力先を変更
python -m lumina_route_finder.gui --output-dir D:\LuminaResults
```

Python版のGUI出力先は、起動時の作業フォルダー内の `outputs/gui/` です。設定は作業フォルダーや出力先とは独立して、リポジトリ直下の `gui-settings.json` に保存します。

GUIはTkinter、Pillow、tkinterdnd2を使用します。Linux / WSLで画像の貼り付けに取得用ツールが必要な場合は `sudo apt install wl-clipboard xclip` で導入できます。利用できない場合は画像ファイルを選択してください。

## CLIで解析する

```powershell
# 画像1枚
python -m lumina_route_finder docs\images\sample_image.jpg

# フォルダーを再帰処理
python -m lumina_route_finder D:\Screenshots --output-dir outputs\samples

# ゴール未到達時は通過数を優先（既定はstage、noneで途中経路を無効化）
python -m lumina_route_finder docs\images\sample_image.jpg --fallback-priority count

# 保存する同率候補の上限を変更
python -m lumina_route_finder docs\images\sample_image.jpg --max-paths 100
```

入力ごとに出力フォルダーを作り、既存の場合は `.1`、`.2` のように別名にします。同率候補は標準で最大20件を保存しますが、同率最長経路の総数は上限に関係なく計算します。GUIの終了時削除設定はCLIには適用しません。

| 出力 | 内容 |
|---|---|
| `result.json` | 成否・最大通過数・候補・同率総数、またはエラー理由 |
| `route.png` | 経路の矢印と通過順を重ねた盤面 |
| `recognized.png` | 認識した接続を赤線で示した確認画像 |
| `board.json` | マス・接続・辺ごとの判定指標 |
| `board.png` | 経路描画前の盤面 |
| `error.png` | 検出できた盤面のエラー箇所 |

JSONのマス位置は `[段階, 列]` の1始まりです。GUIの範囲指定解析では、切り出した `input.png` と元画像の0始まり座標 `[左, 上, 右, 下]` の `input_region` も保存します。右・下の座標は範囲に含めません。

終了コードは、全件正常なら0、認識エラーまたは到達不能なら1、引数不正なら2です。認識できた盤面でゴールに到達できず途中経路が得られた場合は `partial`、起点がない場合や途中経路を無効にした場合は `no_path` として区別します。`partial` も終了コードは1です。途中経路でも通過数・候補・画像を保存し、`goal_reached: false` と1始まりの `reached_stage` を記録します。

### 手動グラフの探索

`board.json` と同じ `nodes`・`edges` 形式のJSONを読み込めます。横辺は1回の記載で双方向になり、段間の辺は上から下に記載します。

```powershell
python -m lumina_route_finder examples\small_board.json --graph --output-dir outputs\graph
```

このサンプルは3段×2列で6アイコンを通過します。画像入力は10段×5列固定です。

## 設定ファイル

GUIはexe横（Python版はリポジトリ直下）の `gui-settings.json` を使用します。初期設定テンプレートは `config/gui-settings.json` です。手動編集はアプリを終了してから行い、再起動してください。CLIはこのGUI設定を読み込みません。

| キー | 初期値 | 内容 |
|---|---|---|
| `delete_outputs_on_exit` | `true` | 今回の生成物を終了時に削除 |
| `avoid_repeated` | `false` | 同じコンテンツの連続を禁止 |
| `exclude_enabled` | `false` | 指定種類の除外を有効にする |
| `excluded_types` | `[]` | 除外する種類のID。無効化しても選択内容は保持 |
| `fallback_priority` | `"stage"` | 未到達時の優先順位。`stage`＝到達段階、`count`＝通過数、`none`＝途中経路を返さない |
| `initial_path_limit` | `20` | 最初に取得する候補数（整数1～1000）。ページを進めると追加取得 |

種類IDは `lumina_route_finder/contents.py` の `CONTENT_NAMES` を参照してください。不正な型・値はその項目の初期値へ戻し、未知の種類IDは除きます。未定義の追加キーは保存時にも保持します。旧出力先の設定を移行する場合は探索設定も引き継ぎ、有効な新設定があれば新設定を優先します。

ソルバーの直接呼び出しは互換性のため `fallback_priority=None` が既定です。途中経路を求める場合は `stage` または `count` を渡してください。GUI・CLIは到達段階優先が既定です。

## テスト

```powershell
python -m unittest discover -s tests -v
```

提供画像のテストは、標準でリポジトリの1階層上にある `sample_image`・`error_images` を参照します。別の場所では、両フォルダーを含む親を指定します。画像がない環境では該当テストをスキップします。画面表示を利用できない環境ではTkのテストをスキップします。

```powershell
$env:LUMINA_SAMPLE_ROOT = 'D:\path\to\images'
python -m unittest discover -s tests -v
```

画像認識、背景・ウィンドウ移動・重なり、倍率・JPEG再圧縮、選択・カーソル遮蔽、範囲指定、GUI、設定移行と削除、経路探索、配布ZIP、リリース添付を検証します。探索結果は小規模ランダムグラフの独立した全経路列挙とも比較します。

認識テンプレートの元画像群はGitに含めず、必要な切り出しPNGを同梱しています。再生成には元画像群が必要です。

```powershell
python tools\build_templates.py ..
```

## Windows配布物をビルドする

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe tools\build_exe.py
```

固定したビルド依存を使い、`dist/` に次の3点を生成します。

- `LuminaRouteFinder.exe`
- `LuminaRouteFinder-Windows-x64.zip`
- `SHA256SUMS.txt`

ZIPはexeと `config/gui-settings.json` に基づく初期設定だけを含み、ビルド環境の個人設定は取り込みません。ビルド後にexeの起動・全画面・切り抜き・貼り付け・範囲指定・倍率タイトルバーの検出と、ZIP展開後の解析・設定保存先・終了後の2ファイル構成を確認します。

## リリースする

1. `pyproject.toml` と `lumina_route_finder/__init__.py` の版番号を揃え、`CHANGELOG.md` に変更内容を記載します。
2. テストを確認し、変更をmainへコミット・pushします。
3. そのコミットへ安定版タグ（`v数字.数字` または `v数字.数字.数字`）を付けてpushします。

```powershell
git tag v1.0.2
git push origin v1.0.2
```

`.github/workflows/release.yml` がWindowsでテスト・ビルド・exeとZIPの動作確認を実行します。3点を下書きリリースへ添付し、ローカルとサーバー側のSHA-256が一致した後に公開します。失敗した場合は下書きを残します。Actionsの「Build and publish Windows release」で既存タグを指定した手動実行もできます。

ローカルの検証のみ行う場合:

```powershell
python tools/publish_release.py v1.0.2 --dry-run
```

手動公開ではGitHub CLIをインストールし、書き込み可能なアカウントで `gh auth login` を行い、タグをリモートへpushした後に `--dry-run` を外します。Actionsでは標準の `GITHUB_TOKEN` と `contents: write` 権限を使用します。

既存の下書きに同内容の添付があれば不足分だけ追加します。異なる添付や公開済みリリースは上書きせず停止します。再ビルドで内容が異なる場合は下書きを確認し、新しいタグでリリースしてください。

## 共有メンテナンスSKILL

`.agents/skills/` に [README更新](../.agents/skills/lumina-readme/SKILL.md)、[Windowsビルド](../.agents/skills/lumina-build/SKILL.md)、[リリース公開](../.agents/skills/lumina-release/SKILL.md) の手順を同梱しています。別ユーザーもリポジトリを取得し、必要なSKILL.mdをエージェントへ指定して利用できます。自分のWindows・Python環境と、公開先への認証を使用してください。

## コード構成

責務ごとの変更先、GUIのView／Controller／Previewの分担、依存方向、既存APIの互換窓口は [コード構成と責務](ARCHITECTURE.md) を参照してください。画面構築・画像操作・表示文・解析・設定・探索を別モジュールに分け、共通の解析処理をCLIとGUIから呼び出します。
