"""
scraper/poster.py — Playwright を利用した X (Twitter) 投稿自動化モジュール

Notion の予約投稿DBから取得したテキスト・画像を
X のツイート作成画面を通して自動投稿します。
"""

import logging
import os
import re
import tempfile
from typing import Optional

import httpx
from playwright.async_api import Page

from scraper.browser import random_wait

logger = logging.getLogger("poster")


def _get_compose_input_selectors() -> list[str]:
    """X の投稿画面で使われ得るテキスト入力セレクタ候補を返す。"""
    return [
        'div[data-testid="tweetTextarea_0"]',
        'div[data-testid="tweetTextarea"]',
        '[data-testid="tweetTextarea_0"]',
        '[data-testid="tweetTextarea"]',
        'div[role="textbox"]',
        'textarea',
        'div[contenteditable="true"]',
        'div[contenteditable="plaintext-only"]',
        'article[role="textbox"]',
        '[role="textbox"]',
    ]


def _get_tweet_button_selectors() -> list[str]:
    """投稿ボタン候補を返す。"""
    return [
        'button[data-testid="tweetButton"]',
        'button[data-testid="postButton"]',
        'button[data-testid="tweetButtonInline"]',
        'button[data-testid="new-tweet-button"]',
        'button:has-text("投稿")',
        'button:has-text("Post")',
    ]


async def _find_visible_locator(page: Page, selectors: list[str], timeout_ms: int = 15000):
    """候補セレクタを順に試し、最初に見つかった visible なロケータを返す。

    2フェーズ方式:
      Phase 1: 全候補を count() で高速スキャン（存在チェックのみ）
      Phase 2: 見つかった候補に対して wait_for(visible) を実行
      Fallback: どれも即座に見つからない場合、全候補を OR 結合して一発待機
    """
    import time as _time

    # Phase 1: 高速スキャン — DOM に存在する候補を探す
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() > 0:
                # Phase 2: 存在する要素が visible になるのを待つ
                await locator.wait_for(state="visible", timeout=timeout_ms)
                return locator
        except Exception:
            # このセレクタは visible にならなかった → 次の候補へ
            continue

    # Fallback: 全候補を OR 結合して一発で待機
    # Playwright の '>>' や ',' 区切りではなく、Promise.race 的に待つ
    combined_selector = ", ".join(selectors)
    locator = page.locator(combined_selector).first
    try:
        await locator.wait_for(state="visible", timeout=timeout_ms)
        return locator
    except Exception as e:
        raise TimeoutError(
            f"候補セレクタが見つかりませんでした "
            f"(timeout={timeout_ms}ms): {selectors}"
        ) from e


async def _open_compose_page(page: Page) -> None:
    """compose 画面を開く。ログイン画面やホーム画面が表示されればフォールバックする。"""
    # まず直接 compose/post を開く
    try:
        await page.goto(
            "https://x.com/compose/post",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        # DOM のレンダリングを待つ
        await random_wait(min_sec=2.0, max_sec=3.0)

        # ログインにリダイレクトされていなければ OK
        if "/login" not in page.url:
            return
    except Exception as e:
        logger.warning("compose/post への直接遷移に失敗: %s", e)

    # フォールバック: ホーム画面経由
    try:
        await page.goto(
            "https://x.com/home",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await random_wait(min_sec=1.5, max_sec=2.5)

        # ホーム画面から compose リンク/ボタンを探す
        home_compose = page.locator(
            'a[href*="/compose/post"], '
            'button[data-testid="new-tweet-button"], '
            'button:has-text("投稿")'
        )
        if await home_compose.count() > 0:
            await home_compose.first.click()
            await random_wait(min_sec=2.0, max_sec=3.0)
            return
    except Exception as e:
        logger.warning("ホーム画面経由のフォールバックに失敗: %s", e)

    # 最終手段: 再度直接遷移
    await page.goto(
        "https://x.com/compose/post",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    await random_wait(min_sec=2.0, max_sec=3.0)


async def _download_images(image_urls: list[str]) -> list[str]:
    """画像URLリストをダウンロードし、一時ファイルパスのリストを返す。

    Args:
        image_urls: ダウンロード対象の画像URLリスト。

    Returns:
        list[str]: 一時ファイルの絶対パスリスト。
    """
    temp_paths: list[str] = []

    for url in image_urls:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            # ファイル拡張子を推定
            content_type = response.headers.get("content-type", "")
            if "png" in content_type:
                suffix = ".png"
            elif "gif" in content_type:
                suffix = ".gif"
            elif "webp" in content_type:
                suffix = ".webp"
            else:
                suffix = ".jpg"

            tmp = tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            )
            tmp.write(response.content)
            tmp.close()
            temp_paths.append(tmp.name)

            logger.debug("画像ダウンロード完了: %s → %s", url[:80], tmp.name)

        except Exception as e:
            logger.error("画像ダウンロード失敗: %s — %s", url[:80], e)

    return temp_paths


def _extract_hashtags(text: str) -> list[str]:
    """本文からハッシュタグ名を抽出する。

    Args:
        text: ツイート本文。

    Returns:
        list[str]: ハッシュタグ名のリスト（# 記号なし）。
    """
    return re.findall(r"#([\wぁ-んァ-ヶ一-龯々ー]+)", text)


def _cleanup_temp_files(paths: list[str]) -> None:
    """一時ファイルを削除する。"""
    for path in paths:
        try:
            os.unlink(path)
        except OSError:
            pass


async def post_tweet(
    page: Page,
    text: str,
    image_urls: list[str] | None = None,
) -> Optional[str]:
    """Playwright でツイートを投稿し、投稿後のツイートURLを返す。

    Args:
        page: Playwright の Page オブジェクト（認証済みセッション）。
        text: ツイート本文（改行・スペース含む）。
        image_urls: 添付画像のURL リスト（Notion S3 URL 等）。

    Returns:
        str | None: 投稿成功時はツイートURL、失敗時は None。
    """
    temp_paths: list[str] = []

    try:
        # ─── 1. 画像のダウンロード ───
        if image_urls:
            temp_paths = await _download_images(image_urls)
            if not temp_paths:
                logger.warning(
                    "画像のダウンロードに全て失敗しました — テキストのみで投稿します"
                )

        # ─── 2. ツイート作成画面を開く ───
        logger.info("📝 ツイート作成画面を表示中...")
        await _open_compose_page(page)

        # テキストエリアの表示を待機（固定データテストIDに依存しないよう複数候補を試す）
        textarea = await _find_visible_locator(page, _get_compose_input_selectors(), timeout_ms=15000)
        await random_wait(min_sec=0.5, max_sec=1.5)

        # ─── 3. 本文を入力（改行を維持） ───
        await textarea.click()
        await random_wait(min_sec=0.3, max_sec=0.7)

        # 改行を Shift+Enter で入力するため、行ごとに分割
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=20)
            if i < len(lines) - 1:
                await page.keyboard.press("Shift+Enter")

        logger.info("本文入力完了 (%d 文字)", len(text))
        await random_wait(min_sec=0.5, max_sec=1.0)

        # ─── 4. 画像を添付 ───
        if temp_paths:
            attached = False

            # 方式A: メディアボタンをクリック → file_chooser で受け取る
            media_button_selectors = [
                '[data-testid="fileInput"]',
                '[aria-label="メディア"]',
                '[aria-label="画像"]',
                '[aria-label="Media"]',
                '[aria-label="Add photos or video"]',
                'button[aria-label*="メディア"]',
                'button[aria-label*="画像"]',
            ]
            for selector in media_button_selectors:
                btn = page.locator(selector)
                try:
                    if await btn.count() > 0:
                        async with page.expect_file_chooser(
                            timeout=5000,
                        ) as fc_info:
                            await btn.first.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(temp_paths)
                        attached = True
                        logger.info(
                            "画像添付完了 (file_chooser方式, %d 枚)",
                            len(temp_paths),
                        )
                        break
                except Exception:
                    continue

            # 方式B: 隠し <input type="file"> に直接セット（フォールバック）
            if not attached:
                for selector in [
                    'input[data-testid="fileInput"]',
                    'input[type="file"]',
                ]:
                    try:
                        candidate = page.locator(selector)
                        if await candidate.count() > 0:
                            await candidate.set_input_files(
                                temp_paths, timeout=10000,
                            )
                            attached = True
                            logger.info(
                                "画像添付完了 (input方式, %d 枚)",
                                len(temp_paths),
                            )
                            break
                    except Exception:
                        continue

            if attached:
                # 添付完了のUI反映を待機
                attachments = page.locator(
                    'div[data-testid="attachments"]'
                )
                try:
                    await attachments.wait_for(
                        state="visible", timeout=15000,
                    )
                except Exception:
                    logger.debug(
                        "添付画像のUI表示待機がタイムアウトしましたが続行します"
                    )
                await random_wait(min_sec=0.5, max_sec=1.5)
            else:
                logger.warning(
                    "画像の添付に失敗しました — テキストのみで投稿を続行します"
                )

        # ─── 5. 投稿ボタンをクリック ───
        tweet_button = await _find_visible_locator(
            page,
            _get_tweet_button_selectors(),
            timeout_ms=10000,
        )

        await tweet_button.click()
        logger.info("投稿ボタンをクリックしました")

        # compose 画面が閉じる（URLが /compose/post から変わる）のを待つ
        try:
            await page.wait_for_url(
                lambda url: "/compose/post" not in url,
                timeout=30000,
            )
        except Exception:
            pass

        await random_wait(min_sec=2.0, max_sec=3.0)

        # ─── 6. ツイートURLを取得 ───
        tweet_url = None

        # 6a. 直接 /status/ ページに遷移した場合（稀だが対応）
        if "/status/" in page.url:
            tweet_url = page.url.split("?")[0]
            logger.info("✅ 投稿成功: %s", tweet_url)
            return tweet_url

        # 6b. トースト通知内のリンクから取得
        #     X は投稿後 "ポストを送信しました [表示]" のトーストを表示する
        try:
            toast_link = page.locator(
                '[data-testid="toast"] a[href*="/status/"]'
            )
            await toast_link.wait_for(state="visible", timeout=10000)
            href = await toast_link.get_attribute("href")
            if href and "/status/" in href:
                if href.startswith("/"):
                    tweet_url = "https://x.com" + href.split("?")[0]
                else:
                    tweet_url = href.split("?")[0]
                logger.info("✅ 投稿成功 (トーストから取得): %s", tweet_url)
                return tweet_url
        except Exception:
            logger.debug("トースト通知からURLを取得できませんでした")

        # 6c. 自プロフィールの最新ツイートから取得
        try:
            # ナビバーのプロフィールリンクから自分のスクリーンネームを取得
            profile_link = page.locator(
                'a[data-testid="AppTabBar_Profile_Link"]'
            )
            if await profile_link.count() > 0:
                profile_href = await profile_link.get_attribute("href")
                if profile_href:
                    profile_url = (
                        "https://x.com" + profile_href
                        if profile_href.startswith("/")
                        else profile_href
                    )
                    await page.goto(
                        profile_url,
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )
                    await page.wait_for_selector(
                        "article[data-testid='tweet']",
                        timeout=15000,
                    )
                    await random_wait(min_sec=1.0, max_sec=2.0)

                    # 最新ツイートの time 要素の親 <a> からURLを取得
                    first_tweet = page.locator(
                        "article[data-testid='tweet']"
                    ).first
                    time_el = first_tweet.locator("time").first
                    if await time_el.count() > 0:
                        href = await time_el.evaluate(
                            "el => el.closest('a')?.href"
                        )
                        if href and "/status/" in href:
                            tweet_url = href.split("?")[0]
                            logger.info(
                                "✅ 投稿成功 (プロフィールから取得): %s",
                                tweet_url,
                            )
                            return tweet_url
        except Exception as e:
            logger.debug("プロフィールからURLを取得できませんでした: %s", e)

        logger.warning(
            "投稿は送信されましたがURLを取得できませんでした (現在URL: %s)",
            page.url,
        )
        return None

    except Exception as e:
        logger.error("❌ ツイート投稿に失敗: %s", e)
        return None

    finally:
        # ─── 7. 一時ファイルのクリーンアップ ───
        _cleanup_temp_files(temp_paths)
