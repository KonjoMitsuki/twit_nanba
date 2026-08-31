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
        await page.goto(
            "https://x.com/compose/post",
            wait_until="domcontentloaded",
        )

        # テキストエリアの表示を待機
        textarea = page.locator('div[data-testid="tweetTextarea_0"]')
        await textarea.wait_for(state="visible", timeout=15000)
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
            file_input = page.locator('input[data-testid="fileInput"]')
            await file_input.set_input_files(temp_paths)

            # 添付完了を待機
            attachments = page.locator('div[data-testid="attachments"]')
            await attachments.wait_for(state="visible", timeout=30000)

            logger.info("画像添付完了 (%d 枚)", len(temp_paths))
            await random_wait(min_sec=0.5, max_sec=1.5)

        # ─── 5. 投稿ボタンをクリック ───
        tweet_button = page.locator('button[data-testid="tweetButton"]')
        await tweet_button.wait_for(state="visible", timeout=10000)

        # ナビゲーション待機を設定してからクリック
        async with page.expect_navigation(
            url=re.compile(r"/status/\d+"),
            timeout=30000,
            wait_until="domcontentloaded",
        ) as nav_info:
            await tweet_button.click()

        # ─── 6. ツイートURLを取得 ───
        response = await nav_info.value
        tweet_url = page.url

        if "/status/" in tweet_url:
            # クエリパラメータを除去
            tweet_url = tweet_url.split("?")[0]
            logger.info("✅ 投稿成功: %s", tweet_url)
            return tweet_url

        logger.warning(
            "投稿後のURLにstatus/が含まれていません: %s", tweet_url
        )
        return None

    except Exception as e:
        logger.error("❌ ツイート投稿に失敗: %s", e)
        return None

    finally:
        # ─── 7. 一時ファイルのクリーンアップ ───
        _cleanup_temp_files(temp_paths)
