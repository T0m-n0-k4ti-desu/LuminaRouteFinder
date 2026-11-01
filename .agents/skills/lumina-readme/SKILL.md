---
name: lumina-readme
description: LuminaRouteFinderのREADMEや利用案内を、現在の機能と実装に合わせて整理・更新するときに使う。
---

# 利用者向けドキュメントを更新する

リポジトリ直下のREADME.mdと、対象機能の実装・テストを確認する。機能の追加時期ではなく、現在できることと操作手順を書く。過去の変更はCHANGELOG.mdへ、Python・CLI・テスト・ビルド・公開の詳細はdocs/DEVELOPMENT.mdへ置く。

- Windows版のダウンロードから開始し、画像入力、範囲指定、探索条件、結果、撮影条件、エラー対処、保存設定の順に利用者の操作を説明する。
- GUIのラベル・初期値・保存先・エラー時の動作はlumina_route_finder/gui.pyとsession.pyで確認する。
- CLIの引数は `python -m lumina_route_finder --help` とguiモジュールの `--help` で確認する。
- サンプルはdocs/images/とtests/fixtures/の共有ファイルを参照する。個人の画像・絶対パス・未コミットの素材に依存させない。
- 公開物の名前はtools/package_release.py・tools/build_exe.py・tools/publish_release.pyと照合する。リンク先の所有者・リポジトリは利用中のremoteに合わせ、未公開の配布物を公開済みと書かない。

変更したMarkdownの相対リンクと画像パスを確認し、 `git diff --check` を実行する。文章だけの変更には不要な画像認識テストを追加しない。依頼で指定されたブランチ・コミット・PRの範囲を守り、既存のユーザー変更を含めない。
