---
name: lumina-release
description: LuminaRouteFinderの版番号更新、タグ作成、GitHub Actionsによるexe・ZIP・チェックサムのリリース公開を依頼されたときに使う。
---

# GitHub Releasesへ公開する

公開することと対象リポジトリ・版番号が依頼の範囲にあることを確認する。ユーザーがすでに公開を依頼していれば同じ確認を繰り返さない。PR作成だけを依頼された場合は公開しない。

docs/DEVELOPMENT.md、.github/workflows/release.yml、tools/publish_release.py、git statusとremoteを確認する。別ユーザーは自身のGitHub認証を使い、 `gh auth status` などで対象への書き込み権限を確認する。GitHub CLIがない場合はActions画面から手動実行できる。認証情報をコード・設定・ログへ保存しない。個人の認証キャッシュや作者のリポジトリ名を前提にしない。

- pyproject.tomlとlumina_route_finder/__init__.pyの版番号を揃え、CHANGELOG.mdに前回公開以降の変更をまとめる。READMEには現在の使い方を書く。
- 公開するコミットを検証し、依頼に従ってpushする。既存のタグや公開済み添付は上書きしない。
- 対象コミットへ新しい安定版タグ（v数字.数字 または v数字.数字.数字）を付けてpushする。タグpushは公開処理を開始するので、ビルドのみの場合は実行しない。
- Actionsのrelease.ymlを追跡する。成功条件はテスト、Windowsビルド、exeと展開後ZIPの動作確認、3添付のチェックサム照合と公開の完了。

失敗時は、まず失敗したステップとログ・リリースの状態を確認する。Windowsでは公開CLIのUTF-8設定と短縮パスに注意する。作成直後の下書きや添付のAPI反映には待ちが入る。tools/publish_release.pyが安全に再利用できるのは同内容の下書き添付だけで、公開済みリリースや異なる添付は変更しない。

同じ原因のまま再実行を繰り返さず、必要な修正を検証してから再開する。Actionsの手動実行ではワークフローのブランチと入力タグが異なる場合があるため、実際にcheckoutされるコミット・公開スクリプトの版を確認する。公開後の既存タグの付け替えで修正しない。

手動公開する場合はWindowsビルドの検証後に、対象を明示して実行する。

```powershell
python tools/publish_release.py v1.2.3 --repo OWNER/REPO --dry-run
# 公開まで依頼されている場合のみ、検証成功後に--dry-runを外す
```

公開後、対象リポジトリのリリースにexe・Windows-x64.zip・SHA256SUMS.txtがあることを確認する。配布リンクから取得でき、チェックサムとZIPの2ファイル構成が一致することを確認し、実際の版番号と公開URLを報告する。
