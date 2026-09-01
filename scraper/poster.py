"""
scraper/poster.py — Playwright を利用した X (Twitter) 投稿自動化モジュール

Notion の予約投稿DBから取得したテキスト・画像を
X のツイート作成画面を通して高速かつ確実に自動投稿します。
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from typing import Optional

import httpx
from playwright.async_api import Page, Response

logger = logging.getLogger("poster")

# テキストエリアのセレクタ（モーダル・インライン両対応）
TEXTAREA_SELECTOR = (
    '[data-testid="tweetTextarea_0"], '
    '[data-testid="tweetTextarea_0_label"], '
    'div[role="textbox"][contenteditable="true"], '
    'div.public-DraftEditor-content'
)

# 投稿ボタンのセレクタ
TWEET_BUTTON_SELECTOR = (
    'button[data-testid="tweetButton"], '
    'button[data-testid="tweetButtonInline"], '
    'button[data-testid="postButton"], '
    'button:has-text("ポストする"), '
    'button:has-text("投稿する")'
)

# ファイル入力のセレクタ
FILE_INPUT_SELECTOR = (
    'input[data-testid="fileInput"], '
    'input[type="file"][accept*="image"], '
    'input[type="file"]'
)


async def _download_single_image(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """単一画像をダウンロードして一時ファイルパスを返す。"""
    try:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "png" in content_type:
            suffix = ".png"
        elif "gif" in content_type:
            suffix = ".gif"
        elif "webp" in content_type:
            suffix = ".webp"
        else:
            suffix = ".jpg"

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(response.content)
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.error("画像ダウンロード失敗: %s — %s", url[:80], e)
        return None


async def _download_images(image_urls: list[str]) -> list[str]:
    """画像URLリストを並行ダウンロードし、一時ファイルパスのリストを返す。"""
    if not image_urls:
        return []

    async with httpx.AsyncClient(timeout=20.0) as client:
        tasks = [_download_single_image(client, url) for url in image_urls]
        results = await asyncio.gather(*tasks)

    temp_paths = [r for r in results if r is not None]
    logger.info("画像ダウンロード完了 (%d/%d 枚)", len(temp_paths), len(image_urls))
    return temp_paths


def _extract_hashtags(text: str) -> list[str]:
    """本文からハッシュタグ名を抽出する。"""
    return re.findall(r"#([\wぁ-んァ-ヶ一-龯々ー]+)", text)


def _cleanup_temp_files(paths: list[str]) -> None:
    """一時ファイルを削除する。"""
    for path in paths:
        try:
            os.unlink(path)
        except OSError:
            pass


def _extract_tweet_url_from_graphql(json_data: dict) -> Optional[str]:
    """CreateTweet の GraphQL レスポンスからツイートURLを構築する。"""
    try:
        # パターン: data -> create_tweet -> tweet_results -> result
        data = json_data.get("data", {})
        create_tweet = data.get("create_tweet", {})
        result = create_tweet.get("tweet_results", {}).get("result", {})
        if not result and "create_tweet_v2" in data:
            result = data.get("create_tweet_v2", {}).get("tweet_results", {}).get("result", {})

        rest_id = result.get("rest_id")
        if not rest_id:
            return None

        # 投稿ユーザーのスクリーンネーム取得（フォールバックあり）
        screen_name = (
            result.get("core", {})
            .get("user_results", {})
            .get("result", {})
            .get("legacy", {})
            .get("screen_name")
        )
        if screen_name:
            return f"https://x.com/{screen_name}/status/{rest_id}"
        return f"https://x.com/i/status/{rest_id}"
    except Exception as e:
        logger.debug("GraphQLパースエラー: %s", e)
        return None


async def post_tweet(
    page: Page,
    text: str,
    image_urls: list[str] | None = None,
) -> Optional[str]:
    """Playwright でツイートを高速に投稿し、投稿後のツイートURLを返す。

    Args:
        page: Playwright の Page オブジェクト（認証済みセッション）。
        text: ツイート本文（改行・スペース含む）。
        image_urls: 添付画像のURL リスト（Notion S3 URL 等）。

    Returns:
        str | None: 投稿成功時はツイートURL、失敗時は None。
    """
    temp_paths: list[str] = []

    try:
        # ─── 1. 画像の並行ダウンロード ───
        if image_urls:
            temp_paths = await _download_images(image_urls)

        # ─── 2. ツイート作成画面へ移動 ───
        logger.info("📝 ツイート作成画面へ移動中...")
        await page.goto(
            "https://x.com/compose/post",
            wait_until="domcontentloaded",
            timeout=20000,
        )

        # テキストエリアの表示を待機（最大15秒）
        textarea = page.locator(TEXTAREA_SELECTOR).first
        try:
            await textarea.wait_for(state="visible", timeout=15000)
        except Exception:
            # もし /compose/post で開かなかった場合、サイドバーの「ポストする」ボタンをクリックしてみる
            logger.warning("テキストエリアが即座に見つからなかったため、新規投稿ボタンの探索を試みます...")
            compose_btn = page.locator(
                'a[data-testid="SideNav_NewTweet_Button"], '
                'a[href="/compose/post"], '
                'button[data-testid="SideNav_NewTweet_Button"]'
            ).first
            if await compose_btn.count() > 0:
                await compose_btn.click()
            await textarea.wait_for(state="visible", timeout=10000)

        # ─── 3. 本文の高速入力 ───
        await textarea.click()
        # 改行を含むテキストを一気に入力
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=5)
            if i < len(lines) - 1:
                await page.keyboard.press("Shift+Enter")

        logger.info("本文入力完了 (%d 文字)", len(text))

        # ─── 4. 画像の高速添付 ───
        if temp_paths:
            file_input = page.locator(FILE_INPUT_SELECTOR).first
            try:
                # 隠し input に直接セット（最速）
                await file_input.set_input_files(temp_paths, timeout=3000)
                logger.info("画像添付完了 (直接セット: %d 枚)", len(temp_paths))
            except Exception:
                # フォールバック: ファイルチューザー経由
                try:
                    async with page.expect_file_chooser(timeout=3000) as fc_info:
                        media_btn = page.locator('[aria-label="メディア"], [aria-label="画像"], button[aria-label*="メディア"]').first
                        await media_btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(temp_paths)
                    logger.info("画像添付完了 (file_chooser: %d 枚)", len(temp_paths))
                except Exception as e:
                    logger.warning("画像添付に失敗しました（テキストのみで続行）: %s", e)

            # 添付画像プレビューの表示を短時間待機
            try:
                await page.locator('div[data-testid="attachments"]').wait_for(
                    state="visible", timeout=5000
                )
            except Exception:
                pass

        # ─── 5. 投稿ボタンをクリック & GraphQL / レスポンス傍受 ───
        tweet_button = page.locator(TWEET_BUTTON_SELECTOR).first
        await tweet_button.wait_for(state="visible", timeout=5000)

        posted_tweet_url: Optional[str] = None

        # GraphQL CreateTweet のレスポンスを拾うハンドラ
        async def handle_response(response: Response):
            nonlocal posted_tweet_url
            if posted_tweet_url:
                return
            if "/graphql/" in response.url and "CreateTweet" in response.url:
                try:
                    json_body = await response.json()
                    url = _extract_tweet_url_from_graphql(json_body)
                    if url:
                        posted_tweet_url = url
                        logger.info("⚡ GraphQL CreateTweet レスポンスからURLを即座に取得: %s", url)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            await tweet_button.click()
            logger.info("投稿ボタンをクリックしました")

            # GraphQL レスポンスまたは compose 画面終了を待機（最大8秒）
            for _ in range(16):
                if posted_tweet_url:
                    break
                await asyncio.sleep(0.5)

        finally:
            page.remove_listener("response", handle_response)

        # ─── 6. URL のフォールバック取得 ───
        if posted_tweet_url:
            logger.info("✅ 投稿成功: %s", posted_tweet_url)
            return posted_tweet_url

        # 6a. 画面遷移後の URL から判定
        if "/status/" in page.url:
            url = page.url.split("?")[0]
            logger.info("✅ 投稿成功 (遷移URL): %s", url)
            return url

        # 6b. トースト通知から判定（短時間）
        try:
            toast_link = page.locator('[data-testid="toast"] a[href*="/status/"]').first
            if await toast_link.count() > 0:
                href = await toast_link.get_attribute("href")
                if href and "/status/" in href:
                    url = "https://x.com" + href.split("?")[0] if href.startswith("/") else href.split("?")[0]
                    logger.info("✅ 投稿成功 (トーストから取得): %s", url)
                    return url
        except Exception:
            pass

        # 6c. プロフィールから最新ツイート取得（最終フォールバック）
        try:
            profile_link = page.locator('a[data-testid="AppTabBar_Profile_Link"]').first
            if await profile_link.count() > 0:
                profile_href = await profile_link.get_attribute("href")
                if profile_href:
                    profile_url = f"https://x.com{profile_href}" if profile_href.startswith("/") else profile_href
                    await page.goto(profile_url, wait_until="domcontentloaded", timeout=10000)
                    first_tweet = page.locator("article[data-testid='tweet']").first
                    await first_tweet.wait_for(state="visible", timeout=5000)
                    time_el = first_tweet.locator("time").first
                    if await time_el.count() > 0:
                        href = await time_el.evaluate("el => el.closest('a')?.href")
                        if href and "/status/" in href:
                            url = href.split("?")[0]
                            logger.info("✅ 投稿成功 (自プロフィールから取得): %s", url)
                            return url
        except Exception as e:
            logger.debug("プロフィールからのURL取得失敗: %s", e)

        logger.warning("投稿は実行されましたが、URLを取得できませんでした (現在のURL: %s)", page.url)
        return None

    except Exception as e:
        logger.error("❌ ツイート投稿に失敗: %s", e)
        return None

    finally:
        # ─── 7. 一時ファイルのクリーンアップ ───
        _cleanup_temp_files(temp_paths)

