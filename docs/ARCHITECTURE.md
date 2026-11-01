# コード構成と責務

実装は機能ごとのパッケージに分けています。新しいコードは互換窓口ではなく、以下の実装モジュールを参照してください。

```text
lumina_route_finder/
  domain/       探索、評価、コンテンツ定義、盤面座標
  application/  解析の組み立て、認識の再利用、手動補正、CLI
  recognition/  盤面位置、格子、接続線、種類の認識、画像検証
  rendering/    経路・認識確認・未到達診断の画像描画
  storage/      画像・結果・設定の入出力、今回の出力管理
  desktop/      クリップボード、候補の保存・コピー
  ui/           Tk画面、操作、プレビュー、設定ダイアログ
  shared/       エラー定義、メッセージ、同梱データのパス
  assets/       同梱する認識テンプレート

tools/
  assets/       テンプレート作成
  build/        exeビルド、exe・ZIPの動作確認
  release/      ZIP作成、チェックサム検証、リリース公開
```

## 変更する場所

| 変更内容 | 主な実装 |
|---|---|
| 最大経路・途中経路・重み評価 | `domain/solver.py` |
| 種類のID・名前、盤面座標と接続候補 | `domain/catalog.py`、`domain/geometry.py` |
| 解析手順・範囲指定・条件比較 | `application/analysis.py` |
| 認識結果のキャッシュ・再探索 | `application/session.py` |
| 認識結果の手動補正・Undo | `application/review.py` |
| CLI引数 | `application/cli.py` |
| 盤面位置と格子 | `recognition/location.py`、`recognition/grid.py` |
| 接続線、種類、欠損・遮蔽の検証 | `recognition/connections.py`、`contents.py`、`validation.py` |
| 経路・診断・認識確認の描画 | `rendering/routes.py`、`diagnostics.py`、`recognition.py` |
| 設定の検証・保存・移行 | `storage/settings.py` |
| 今回の出力登録・終了時削除 | `storage/session_outputs.py` |
| 画像・JSONなどの保存 | `storage/images.py`、`artifacts.py`、`file_safety.py` |
| 貼り付け・候補保存とコピー | `desktop/clipboard.py`、`route_export.py` |
| 画面構築・操作・画像表示 | `ui/view.py`、`controller.py`、`preview.py` |
| 表示文、設定画面 | `ui/presentation.py`、`preferences.py` |
| エラーコード・共通例外・日本語文 | `shared/errors.py`、`messages.py` |

## 依存関係

`domain/` はOpenCV、Tk、ファイル保存に依存しません。`application/` が認識・探索・描画・保存を組み合わせ、GUIとCLIから共用します。解析とCLIはGUIを読み込みません。手動補正のデータ操作も画像描画から分離しています。

GUIの `ApplicationView` は画面構築、`ImagePreview` は画像表示と座標変換、`Application` は操作と非同期処理を担当します。Tkの操作は主スレッドで行い、解析ワーカーから結果をキューで受け取ります。境界は `tests/test_architecture.py` で検証します。

## 起動口と互換性

`python -m lumina_route_finder`、`python -m lumina_route_finder.gui`、`launch_gui.pyw` は従来どおり使えます。

ルートの `analysis.py`、`cli.py`、`recognize.py`、`settings.py`、`session.py`、`image_io.py`、`errors.py`、`error_messages.py` は既存の公開インポートを維持する窓口です。`gui.py` と `solver.py` も公開窓口として残します。内部コードは機能別パッケージを直接参照します。テストで関数を差し替える場合も、実際に使用するモジュール側を対象にしてください。

開発用コマンドは `python -m tools.build.build_exe`、`python -m tools.assets.build_templates`、`python -m tools.release.publish` に整理しています。従来の `python tools/build_exe.py` なども互換ランチャーとして使用できます。

## データとエラー

認識用データは引き続き `lumina_route_finder/assets/`、Python版設定はリポジトリ直下、exe版設定はexe横です。設定をoutputsへ戻す変更はありません。

`shared.errors` がエラーコードと共通例外を定義し、`shared.messages` が利用者向け文を整形します。CLIとGUIの処理境界で例外を共通結果に変換します。探索の `partial` と `no_path` はエラー例外に変換しません。

配置変更では探索条件・設定形式・出力形式を変更しません。通常・条件付き・範囲指定・不正画像の4ケースについて、変更前後のJSONとPNGがバイト単位で一致することを確認しています。
