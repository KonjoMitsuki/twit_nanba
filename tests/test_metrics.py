from scraper.metrics import _extract_user_followers_count


def test_extract_user_followers_count_from_explicit_user_path():
    tweet_result = {
        "core": {
            "user_results": {
                "result": {
                    "legacy": {
                        "followers_count": 12345,
                    }
                }
            }
        },
        "legacy": {"favorite_count": 99},
    }

    assert _extract_user_followers_count(tweet_result) == 12345


def test_extract_user_followers_count_falls_back_to_recursive_scan():
    tweet_result = {
        "data": {
            "user": {
                "result": {
                    "legacy": {
                        "followers_count": 678,
                    }
                }
            }
        }
    }

    assert _extract_user_followers_count(tweet_result) == 678


def test_extract_user_followers_count_from_relationship_counts():
    """新しい X GraphQL API 構造: legacy が廃止され relationship_counts に移行。"""
    tweet_result = {
        "core": {
            "user_results": {
                "result": {
                    "__typename": "User",
                    "relationship_counts": {
                        "followers": 9876,
                        "following": 123,
                    },
                    "rest_id": "12345",
                }
            }
        },
        "legacy": {"favorite_count": 99},
    }

    assert _extract_user_followers_count(tweet_result) == 9876

