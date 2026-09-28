# twit_nanba カレンダーUI レスポンシブ・リファクタリング仕様指示書
## 対象: スマホ表示時のヘッダー / サマリー / カレンダーグリッド

### 0. 改修目的

現在の `web/index.html` + `web/app.js` + `web/styles.css` は、PCの横幅を前提としたレイアウトになっており、スマホ幅（〜430px程度）で見ると崩れる。

添付スクリーンショット（LINEアプリ内ブラウザで表示したもの）で確認できる具体的な崩れ:

- ヘッダー右上の「🔍 新着チェック」ボタンが極端に狭い領域に押し込まれ、文字が縦に一文字ずつ折り返されている（「着/手/チ/ェ/ッ/ク」のように積み上がる）
- サマリー（FOLLOWERS / POSTS / LIKES / REPOSTS）の4カラムがそのまま横に並び、REPOSTSのカラムがヘッダーのボタンと重なって見える
- カレンダーの各日セル内で `460 likes` のようなテキストが折り返され、隣の要素（フォロワー増減やpost数の数字）と文字が連結して見える（`likes3…` のような表示）
- 1日に複数投稿がある日は、サムネイルが縦に複数積まれてセルの高さが暴れ、月全体のリズムが崩れる

今回の改修では、**PC表示の見た目・機能は一切変更しない**。変更するのはスマホ幅（後述のブレークポイント以下）のときの表示のみとする。

参考として、添付の2枚目の画像（カレンダーアプリのイラスト付き月表示）のような「1マス＝1枚のイラストが主役で、文字情報は最小限」というレイアウトを目標イメージとする。ここに、いいね数・投稿時刻などの文字情報を重ねて追加するイメージ。

---

# 1. 対象ファイル

```text
web/index.html
web/app.js
web/styles.css
```

API（`api/main.py`, `storage/app_db.py`）・DB・`web/detail.html` / `web/detail.js`（作品詳細ページ）は今回の対象外。カレンダーAPIのレスポンス仕様（`/api/calendar`）は変更しない。

---

# 2. ブレークポイント

既存の `styles.css` はグラフ部分のみ `@media (max-width:700px)` を持っている。今回のカレンダー/ヘッダー/サマリー改修も同じ値に揃える。

```css
@media (max-width: 700px) {
  /* カレンダー・サマリー・ヘッダーのスマホ対応をここに追加 */
}
```

これより広い画面（PC/タブレット横）は現状の見た目・DOM構造を一切変更しない。

---

# 3. スマホ表示で優先する情報（最重要方針）

ユーザー指定の優先度は以下の4つのみ。

```text
1. イラスト（サムネイル画像）
2. いいね数
3. フォロワー推移（日次のfollowers_delta）
4. 投稿時刻
```

それ以外（RT数、投稿件数の表示、「likes」等のラベル文字）は、**窮屈なら消してよい／消す**。具体的な扱いは以下の通り固定する。

| 項目 | スマホでの扱い |
|---|---|
| サムネイル画像 | 必ず表示。1マスの主役として大きく表示 |
| いいね数 | 必ず表示。ただし「likes」のようなラベル文字は付けない。数字のみ |
| いいね数の色 | 赤寄りのピンク（下記トークン参照）に変更 |
| RT（リポスト）数 | **非表示**（`art-meta` の `↗ RT数` をスマホ幅では出力しない） |
| 投稿時刻 | 必ず表示。`17:00` のような時刻のみ、小さめの文字でよい |
| フォロワー増減（day-footer） | 表示を維持する（`+21` のような数値のみでよく、「followers」の単語は省略可） |
| 投稿件数（`N posts`） | スマホでは非表示にしてよい（1マスに複数投稿がある場合は後述の「+N」バッジで代替） |
| 文字サイズ | 全体的に小さくしてよい（8〜10px程度まで許容） |

---

# 4. ヘッダー（`.hero` / `.month-controls`）のスマホ対応

## 4.1 現状の問題

`.hero` は `display:flex;justify-content:space-between;align-items:end` で、左側の見出し（`h1#month-title`）と右側の `.month-controls`（← / 今日 / → / 🔍新着チェック）が横並びのまま。`h1` は `clamp(2.3rem,5vw,5.4rem)` で大きいため、スマホ幅では `.month-controls` に残る横幅がほぼゼロになり、ボタン内テキストが1文字ずつ折り返される。

## 4.2 対応方針

スマホ幅では、

```text
.hero を縦積みにする（flex-direction: column; align-items: stretch;）
.month-controls を横幅いっぱいの行にして flex-wrap: wrap を許可
```

さらに、ボタン内テキストの折り返し自体を防ぐため、`.icon-button, .today-button` に `white-space: nowrap` を追加する（これはPC/スマホ共通で追加してよい安全な修正）。

```css
@media (max-width: 700px) {
  .hero { flex-direction: column; align-items: stretch; gap: 16px; padding: 32px 0 20px; }
  .hero h1 { font-size: clamp(1.6rem, 8vw, 2.4rem); }
  .month-controls { display: flex; flex-wrap: wrap; gap: 6px; }
  .month-controls .today-button,
  .month-controls .icon-button { flex: 1 1 auto; min-width: 0; }
}
.icon-button, .today-button, .x-link { white-space: nowrap; }
```

「🔍 新着チェック」ボタンだけ幅を取りすぎる場合は、スマホ幅ではラベルを短縮してよい（例: `🔍 新着チェック` → `🔍 チェック`、または絵文字のみ）。文言短縮を行う場合は `app.js` 側のテキスト設定箇所（`patrolBtn.textContent`）とHTML側の初期表示の両方を統一すること。

---

# 5. サマリー（`.summary` KPI）のスマホ対応

## 5.1 現状の問題

`.summary` は `grid-template-columns:repeat(4,1fr)` で固定4カラム。スマホ幅では1カラムあたりが狭すぎて数値（`13,277` のような5桁の数字）が折り返す。

## 5.2 対応方針

スマホ幅では2×2グリッドに変更し、フォントサイズを縮小する。

```css
@media (max-width: 700px) {
  .summary { grid-template-columns: repeat(2, 1fr); }
  .summary-item { padding: 12px 10px; }
  .summary-item strong { font-size: 1.3rem; }
  .summary-item span, .summary-item small { font-size: 0.6rem; }
}
```

4項目のうち `REPOSTS` はカレンダー本体（day-cellの中）では非表示にするが、**サマリー欄では引き続き表示してよい**（月間の合計値であり、day-cellの折り返し崩れの原因ではないため）。もしサマリー欄でも「N周分減らしたい」という要望が出た場合のみ、REPOSTSを2×2の4番目から外して2×1にする対応を検討する（今回は必須ではない）。

---

# 6. カレンダー Day-cell のスマホ対応（メイン改修）

## 6.1 目標イメージ（添付2枚目の画像を踏襲）

```text
┌───────────┐
│ 3         │ ← 日付番号（小さく、左上にオーバーレイ）
│           │
│  [image]  │ ← サムネイル画像がマスの大半を占める
│           │
│ 256  17:00│ ← いいね数（ピンク・ラベルなし）＋ 投稿時刻（下部にオーバーレイ）
└───────────┘
   +21          ← その日のフォロワー増減（マスの外、下に小さく）
```

- 画像を主役にして、テキストは最小限のオーバーレイに変える
- 1マスに複数投稿がある場合も、スマホでは**代表1件のサムネイルのみ**を大きく出し、右上などに `+2` のような残り件数バッジを出す（PCのように3枚積み上げない）

## 6.2 `app.js` 側の変更

現在の `renderCalendar()` は、日ごとに最大3件の `art-card` を積み上げて表示している（`dayData.artworks.slice(0, 3)`）。

```js
// 現状（抜粋）
const cards = dayData.artworks.slice(0, 3).map(art => ...).join('');
const more = dayData.artworks.length > 3 ? `<span class="more">+${...}</span>` : '';
```

PC表示ではこの「最大3件積み上げ」を維持する。スマホ表示は**CSSだけで対応しきれない**ため、JS側で以下を追加する。

1. `art-meta` 内のRT表示 `<span>↗ ${shortNumber(art.retweets)}</span>` を削除し、代わりに `<span class="art-rt">↗ ${shortNumber(art.retweets)}</span>` のように**クラス付きで出力を残す**。表示/非表示はCSSの `display:none`（スマホ幅のみ）で制御する。RT自体のデータをHTMLから完全に消すのではなく、CSSで隠す方式にすることで、将来「PCではRT表示・スマホでは非表示」のような要望差分にも対応しやすくする。
2. いいね数の `<b>${shortNumber(art.likes)} likes</b>` を `<b class="art-likes">${shortNumber(art.likes)}</b><span class="art-likes-label"> likes</span>` のように分割する。スマホ幅では `.art-likes-label` を `display:none` にし、`.art-likes` の文字色をピンクに変える。
3. 1マス内の2件目以降（`slice(0,3)` の2番目・3番目）に、スマホ幅専用のクラス `art-card--extra` を付与する。CSS側でスマホ幅のときだけ `.art-card--extra { display: none; }` にし、代わりに1件目の `art-card` に `+N`（`dayData.artworks.length - 1`）バッジを重ねて出す。

具体的な修正イメージ:

```js
function renderCalendar(data) {
  const calendar = document.querySelector('#calendar');
  const first = new Date(data.year, data.month - 1, 1);
  const daysInMonth = new Date(data.year, data.month, 0).getDate();
  const byDate = Object.fromEntries(data.days.map(day => [day.date, day]));
  calendar.innerHTML = '';
  for (let i = 0; i < first.getDay(); i++) calendar.append(document.createElement('div'));
  for (let day = 1; day <= daysInMonth; day++) {
    const dateKey = `${data.year}-${String(data.month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const dayData = byDate[dateKey];
    const cell = document.createElement('div');
    cell.className = 'day-cell';
    cell.innerHTML = `<div class="day-number">${day}</div>`;
    if (dayData) {
      const extraCount = Math.max(dayData.artworks.length - 1, 0);
      const cards = dayData.artworks.slice(0, 3).map((art, index) => `
        <a class="art-card${index > 0 ? ' art-card--extra' : ''}" href="/artworks/${art.id}">
          <div class="thumb">
            ${art.image_url ? `<img src="${art.image_url}" alt="">` : '<span>NO IMAGE</span>'}
            ${index === 0 && extraCount > 0 ? `<span class="art-extra-badge">+${extraCount}</span>` : ''}
          </div>
          <div class="art-meta">
            <b class="art-likes">${shortNumber(art.likes)}</b><span class="art-likes-label"> likes</span>
            <span class="art-rt">↗ ${shortNumber(art.retweets)}</span>
          </div>
          <small class="art-time">${new Date(art.posted_at).toLocaleTimeString('ja-JP', {hour: '2-digit', minute: '2-digit'})}</small>
        </a>`).join('');
      const more = dayData.artworks.length > 3
        ? `<span class="more">+${dayData.artworks.length - 3} more</span>` : '';
      cell.insertAdjacentHTML('beforeend', `
        <div class="artworks">${cards}${more}</div>
        <div class="day-footer">
          <span class="delta ${dayData.followers_delta > 0 ? 'positive' : ''}">
            ${dayData.followers_delta == null ? '—' : `${dayData.followers_delta >= 0 ? '+' : ''}${number(dayData.followers_delta)} followers`}
          </span>
          <span class="post-count">${dayData.artworks.length} post${dayData.artworks.length === 1 ? '' : 's'}</span>
        </div>`);
    }
    calendar.append(cell);
  }
}
```

（`day-footer` の `followers` 単語 / `post-count` 全体は、スマホ幅ではCSSで簡略・非表示にする。`extraCount` はPC幅では使わない値なので、`art-extra-badge` はデフォルト非表示にしておき、スマホ幅のときだけ見せる。）

## 6.3 `styles.css` 側の変更（スマホ幅のみ）

```css
@media (max-width: 700px) {
  /* --- day-cell 全体 --- */
  .day-cell { min-height: 0; padding: 4px; }
  .day-number {
    position: absolute; z-index: 2; margin: 4px;
    background: rgba(255,255,255,.82); padding: 1px 4px; font-size: .6rem;
  }

  /* --- 1マスの中の複数カードをオーバーレイ1枚に集約 --- */
  .artworks { position: relative; margin-top: 0; }
  .art-card { position: relative; margin-bottom: 0; padding: 0; }
  .art-card--extra { display: none; }
  .more { display: none; }

  .thumb { aspect-ratio: 1; position: relative; }
  .art-extra-badge {
    position: absolute; top: 4px; right: 4px; z-index: 2;
    background: rgba(32,34,30,.72); color: var(--white);
    font: 600 .6rem 'DM Mono', monospace; padding: 1px 5px;
  }

  /* --- いいね数・時刻をサムネイルの下にオーバーレイ --- */
  .art-meta {
    position: absolute; left: 0; right: 0; bottom: 14px; z-index: 2;
    justify-content: flex-start; gap: 2px; padding: 2px 4px;
    background: linear-gradient(to top, rgba(255,255,255,.9), rgba(255,255,255,0));
  }
  .art-likes { color: #e8447a; font-size: .68rem; }
  .art-likes-label { display: none; }
  .art-rt { display: none; }
  .art-time {
    position: absolute; left: 0; right: 0; bottom: 0; z-index: 2;
    text-align: right; padding: 0 4px 2px; font-size: .58rem;
  }

  /* --- day-footer は最小限に --- */
  .day-footer { font-size: .58rem; padding-top: 3px; }
  .day-footer .post-count { display: none; }
  .delta { white-space: nowrap; }
}
```

`--chart-accent`（既存のコーラル `#f2785d`）とは別に、いいね数専用の色を使う。既存の `:root` トークンに以下を1行追加してもよい（必須ではなく、直書きでも可）。

```css
:root{ --likes-pink:#e8447a; }
```

追加した場合は `.art-likes{ color: var(--likes-pink); }` に差し替える。

---

# 7. 実装順序（推奨）

```text
1. .icon-button, .today-button, .x-link に white-space:nowrap を追加（PC/スマホ共通・安全な修正）
2. @media (max-width:700px) ブロックをstyles.cssに新設し、ヘッダー(.hero)のスマホレイアウトを実装
3. サマリー(.summary)のスマホレイアウト(2×2)を実装
4. app.js の renderCalendar() を、art-likes / art-likes-label / art-rt / art-card--extra / art-extra-badge / art-time / post-count のクラス構成に合わせて修正
5. styles.css の day-cell 以下のスマホ対応を実装
6. 実機 or ブラウザのスマホエミュレータ(375px, 390px, 414px)で確認
7. PC幅(1280px以上)で崩れていないことを確認
```

---

# 8. 受け入れ条件

## 8.1 スマホ幅（〜700px）

- ヘッダーのボタン文字が縦に折り返されない
- サマリーの数値・ラベルが折り返さずに収まる
- カレンダーの各マスで、サムネイル画像がマスの大半を占める
- いいね数が「likes」という単語なしで、ピンク系の色で表示される
- RT（リポスト）数がカレンダー上に表示されない
- 投稿時刻が表示される
- その日のフォロワー増減（`+21` など）が表示される
- 1日に複数投稿がある場合、サムネイルが縦に積み上がらず、代表1枚＋`+N`バッジで表現される
- 文字の重なり・はみ出しが発生しない

## 8.2 PC幅（700px超）

- 現在の見た目・DOM構造・動作が一切変化しない
- 1日3件までのカード積み上げ表示、RT表示、「likes」ラベル、post数表示、月間サマリー4カラムがすべて従来通り

## 8.3 既存機能への影響なし

- `/api/calendar` のレスポンス仕様は変更しない
- 作品詳細ページ（`detail.html` / `detail.js`）・カルーセル・グラフには一切手を入れない
- `#patrol-now`（新着チェック）ボタンの挙動（クリック→巡回→ポーリング→再読み込み）は変更しない

---

# 9. 変更してよいファイル / 変更しないファイル

変更してよい:

```text
web/index.html   … 必要なら軽微なマークアップ追加のみ（大きな構造変更はしない）
web/app.js       … renderCalendar() のみ
web/styles.css   … 追記のみ（既存の1行圧縮スタイルの書き方に合わせる）
```

変更しない:

```text
web/detail.html
web/detail.js
api/main.py
storage/app_db.py
scraper/
processing/
notion_client_wrapper/
```

---

# 10. 手動確認項目

- [ ] iPhone実機 or Chrome DevToolsのモバイルエミュレータ（iPhone SE / iPhone 14 / Pixel 7 相当）でカレンダーを開く
- [ ] 月をまたいで前後移動しても崩れない
- [ ] 投稿が0件の日、1件の日、2件以上の日、それぞれ表示を確認
- [ ] フォロワー増減が `null` の日に `—` が正しく出る
- [ ] 「🔍 新着チェック」ボタンをタップし、文言が折り返さず「巡回中…」に変わる
- [ ] PC幅（デスクトップブラウザ、ウィンドウ幅1280px程度）で従来通りの見た目であることを確認
- [ ] 700px前後（タブレット幅）でレイアウトが破綻しないことを確認
