# 本番コード更新時のWeb/API自動再起動

`deploy/systemd/` の2つのunitは、`~/twit_nanba` の既存の `twit_nanba.service` 用です。テンプレートの `@PROJECT_ROOT@` は、導入時に実際の絶対パスへ置き換えます。systemdのパス指定では `~` が展開されないため、そのまま記入しないでください。別の環境ではパスとサービス名を変更してください。

## 動作

- `api`、`storage`、`processing`、`scraper`、`notion_client_wrapper` の各ディレクトリ直下の変更と、`config.py`、`.env` の変更をsystemdで監視します。新しくサブディレクトリを追加した場合は、そのパスも監視設定に追加してください。
- 変更を検知すると5秒待ち、既存の `.process.lock` を取得してからWeb/APIだけを再起動します。収集やURL登録が実行中の場合は、ロックが解放されるまで待ちます。
- DB、ログ、画像、認証セッションの更新では再起動しません。`web` の静的ファイルはリクエスト時に読み込まれるため監視しません。ブラウザー側で再読み込みが必要な場合があります。
- Gitの取得、依存パッケージのインストール、収集用cronの変更は行いません。依存関係を変更する更新や、大量のファイルを時間をかけて更新する場合は、先に監視を停止してください。5秒の待機は、更新全体の完了を保証するものではありません。

## 導入

本番にSSH接続し、リポジトリ内のunitファイルを配置します。sudoのパスワードが必要です。

```bash
cd ~/twit_nanba
set -o pipefail
for unit in twit_nanba-code-watch.path twit_nanba-code-restart.service; do
  sed "s|@PROJECT_ROOT@|$HOME/twit_nanba|g" "deploy/systemd/$unit" \
    | sudo tee "/etc/systemd/system/$unit" >/dev/null || break
done
sudo systemctl daemon-reload
sudo systemctl enable --now twit_nanba-code-watch.path
```

配置直後はコードの変更を待ちます。既に更新済みのコードも反映したい場合は、次を実行してください。

```bash
sudo systemctl start twit_nanba-code-restart.service
```

## 確認

```bash
systemctl status twit_nanba-code-watch.path twit_nanba-code-restart.service
journalctl -u twit_nanba-code-restart.service -u twit_nanba.service --since '10 minutes ago'
```

再起動用serviceが処理後に `inactive (dead)` になるのは正常です。監視用pathが `active (waiting)` であることを確認してください。

動作確認は、収集やURL登録の実行中を避けて `touch api/main.py` を実行し、Web/APIのPIDが変わり `/api/health` が成功することを確認します。実際のX投稿やデータ登録は不要です。

## 停止・再開

```bash
sudo systemctl disable --now twit_nanba-code-watch.path
sudo systemctl stop twit_nanba-code-restart.service
# 更新や依存パッケージのインストールを完了してから再起動・監視再開
sudo systemctl start twit_nanba-code-restart.service
sudo systemctl enable --now twit_nanba-code-watch.path
```

監視だけを無効にしても、既に待機・実行中の再起動用serviceは停止しません。そのため停止時は両方を指定します。既存のWeb/APIサービスと収集用cronはそのまま残ります。
