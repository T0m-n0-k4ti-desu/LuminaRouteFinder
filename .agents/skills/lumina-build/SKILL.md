---
name: lumina-build
description: LuminaRouteFinderのWindows用exeと2ファイル構成のZIPを作成・検証するときに使う。
---

# Windows配布物をビルドする

リポジトリ直下を作業場所とし、docs/DEVELOPMENT.md、requirements-build.txt、tools/build_exe.pyを確認する。WindowsとPython 3.11 x64を用意する。個人のユーザー名・既存venv・外部サンプル画像は前提にしない。

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-build\Scripts\python.exe tools/build_exe.py
```

提供されたsample_image/error_imagesがある場合は、その親をLUMINA_SAMPLE_ROOTに指定して追加検証できる。ない場合の該当テストのskipを区別して報告する。Gitに含むfixturesだけで配布物の起動検証は実行できる。

ビルド処理はexeの全画面・切り抜き・貼り付け・範囲指定・倍率ヘッダーを検証し、ZIPを実際に展開して解析・設定保存・終了時の後片付けを確認する。失敗時はログとoutputs/exe-smoke/を確認し、検証を省略して成功扱いにしない。

成功時のdist/配下の配布物は以下の3つ。

- LuminaRouteFinder.exe
- LuminaRouteFinder-Windows-x64.zip
- SHA256SUMS.txt

ZIPはexeと初期設定gui-settings.jsonだけを直下に含む。個人のgui-settings.jsonやoutputsを同梱しない。

```powershell
.\.venv-build\Scripts\python.exe tools/publish_release.py v1.2.3 --dry-run --repo OWNER/REPO
```

この例の版番号とリポジトリは実際の対象に置き換える。dry-runでチェックサム・ZIP内exeの一致を確認する。配布物・venv・生成出力はGitに登録しない。ビルド依頼だけではタグpush・リリース公開は行わない。
