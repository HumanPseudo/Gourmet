from __future__ import annotations

from unittest.mock import Mock, call, patch

from django.conf import settings
from django.test import RequestFactory, TestCase

from gourmet.apps.jukebox.api import (
    add_to_custom_queue,
    add_to_custom_queue_and_play,
    push_to_pear,
    reconcile_custom_queue,
    search,
)
from gourmet.apps.jukebox.models import JukeboxQueueItem
from gourmet.apps.jukebox.schemas import (
    QueueItemIn,
    QueueItemOut,
    SearchIn,
    SearchResultOut,
)
from gourmet.apps.jukebox.services import JukeboxService

SERVICE_PATH = "gourmet.apps.jukebox.services.JukeboxService"
REQUESTS_PATH = "gourmet.apps.jukebox.services"


class SearchEndpointTests(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        JukeboxService._token_cache.clear()

    def test_filter_search_results_extracts_music_cards(self) -> None:
        payload = {
            "responseContext": {"responseId": "abc"},
            "contents": {
                "tabbedSearchResultsRenderer": {
                    "tabs": [
                        {
                            "tabRenderer": {
                                "content": {
                                    "sectionListRenderer": {
                                        "contents": [
                                            {
                                                "musicCardShelfRenderer": {
                                                    "thumbnail": {
                                                        "musicThumbnailRenderer": {
                                                            "thumbnail": {
                                                                "thumbnails": [
                                                                    {
                                                                        "url": "https://i.ytimg.com/vi/p-Z3YrHJ1sU/hqdefault.jpg"
                                                                    }
                                                                ]
                                                            }
                                                        }
                                                    },
                                                    "title": {
                                                        "runs": [
                                                            {
                                                                "text": "Stereo Love (Extended Mix)",  # noqa: E501
                                                                "navigationEndpoint": {
                                                                    "watchEndpoint": {
                                                                        "videoId": "p-Z3YrHJ1sU"  # noqa: E501
                                                                    }
                                                                },
                                                            }
                                                        ]
                                                    },
                                                    "subtitle": {
                                                        "accessibility": {
                                                            "accessibilityData": {
                                                                "label": "Video • Edward Maya & Vika Jigulina • 761 million views • 4 minutes, 13 seconds"  # noqa: E501
                                                            }
                                                        },
                                                        "runs": [
                                                            {"text": "Video"},
                                                            {"text": " • "},
                                                            {"text": "Edward Maya"},
                                                            {"text": " & "},
                                                            {"text": "Vika Jigulina"},
                                                            {"text": " • "},
                                                            {"text": "761M views"},
                                                            {"text": " • "},
                                                            {"text": "4:13"},
                                                        ],
                                                    },
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    ]
                }
            },
        }

        assert JukeboxService.filter_search_results(payload) == [
            SearchResultOut(
                video_id="p-Z3YrHJ1sU",
                title="Stereo Love (Extended Mix)",
                artist="Edward Maya & Vika Jigulina",
                thumbnail_url="https://i.ytimg.com/vi/p-Z3YrHJ1sU/hqdefault.jpg",
                duration="4:13",
            )
        ]

    def test_search_returns_filtered_results(self) -> None:
        request = self.factory.post("/api/jukebox/player/search")
        payload = SearchIn(query="stereo love")
        upstream_response = {
            "contents": {
                "tabbedSearchResultsRenderer": {
                    "tabs": [
                        {
                            "tabRenderer": {
                                "content": {
                                    "sectionListRenderer": {
                                        "contents": [
                                            {
                                                "musicCardShelfRenderer": {
                                                    "title": {
                                                        "runs": [
                                                            {
                                                                "text": "Stereo Love (Extended Mix)",  # noqa: E501
                                                                "navigationEndpoint": {
                                                                    "watchEndpoint": {
                                                                        "videoId": "p-Z3YrHJ1sU"  # noqa: E501
                                                                    }
                                                                },
                                                            }
                                                        ]
                                                    },
                                                    "subtitle": {
                                                        "accessibility": {
                                                            "accessibilityData": {
                                                                "label": "Video • Edward Maya & Vika Jigulina • 761 million views • 4 minutes, 13 seconds"  # noqa: E501
                                                            }
                                                        }
                                                    },
                                                    "thumbnail": {
                                                        "musicThumbnailRenderer": {
                                                            "thumbnail": {
                                                                "thumbnails": [
                                                                    {
                                                                        "url": "https://i.ytimg.com/vi/p-Z3YrHJ1sU/hqdefault.jpg"
                                                                    }
                                                                ]
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }

        with patch(
            f"{SERVICE_PATH}.proxy_request",
            return_value=(200, upstream_response),
        ):
            result = search(request, payload)

        assert result == [
            SearchResultOut(
                video_id="p-Z3YrHJ1sU",
                title="Stereo Love (Extended Mix)",
                artist="Edward Maya & Vika Jigulina",
                thumbnail_url="https://i.ytimg.com/vi/p-Z3YrHJ1sU/hqdefault.jpg",
                duration="4:13",
            )
        ]

    @patch(f"{REQUESTS_PATH}.requests.request")
    @patch(f"{REQUESTS_PATH}.requests.post")
    def test_proxy_request_uses_api_server_token(
        self,
        requests_post: Mock,
        requests_request: Mock,
    ) -> None:
        requests_post.return_value = Mock(
            status_code=200,
            json=lambda: {"accessToken": "token-123"},
            text="",
        )
        requests_request.return_value = Mock(
            status_code=200,
            json=lambda: {"results": []},
            text="",
        )

        status, data = JukeboxService.proxy_request(
            "POST", "search", json={"query": "hello"}
        )

        assert status == 200
        assert data == {"results": []}
        base_url = settings.PEAR_API_URL.split("/api/", 1)[0]
        auth_url = f"{base_url}/auth/{settings.PROJECT_NAME}"
        requests_post.assert_called_once_with(auth_url, timeout=5)
        requests_request.assert_called_once_with(
            "POST",
            f"{settings.PEAR_API_URL.rstrip('/')}/search",
            json={"query": "hello"},
            headers={"Authorization": "Bearer token-123"},
            timeout=5,
        )

    def test_sync_queue_to_player_rebuilds_remote_queue(self) -> None:
        first = JukeboxQueueItem.objects.create(
            video_id="one",
            title="One",
            sort_order=0,
        )
        JukeboxQueueItem.objects.create(
            video_id="old",
            title="Old",
            status=JukeboxQueueItem.STATUS_PLAYED,
            sort_order=1,
        )
        second = JukeboxQueueItem.objects.create(
            video_id="two",
            title="Two",
            sort_order=2,
        )

        with patch(
            f"{SERVICE_PATH}.proxy_request",
            side_effect=[
                (204, None),
                (204, None),
                (204, None),
            ],
        ) as proxy_request_mock:
            status, data = JukeboxService.sync_queue_to_player()

        assert status == 204
        assert data is None
        assert proxy_request_mock.call_args_list == [
            call("DELETE", "queue"),
            call("POST", "queue", json={"videoId": first.video_id}),
            call("POST", "queue", json={"videoId": second.video_id}),
        ]

    def test_add_to_custom_queue_and_play_creates_syncs_and_plays(self) -> None:
        request = self.factory.post("/api/jukebox/queue/play")
        payload = {
            "video_id": "p-Z3YrHJ1sU",
            "title": "Stereo Love (Extended Mix)",
            "artist": "Edward Maya & Vika Jigulina",
            "thumbnail_url": "https://i.ytimg.com/vi/p-Z3YrHJ1sU/hqdefault.jpg",
            "duration": "4:13",
        }

        with patch(
            f"{SERVICE_PATH}.proxy_request",
            side_effect=[
                (204, None),
                (204, None),
                (204, None),
                (204, None),
            ],
        ) as proxy_request_mock:
            status, item = add_to_custom_queue_and_play(
                request,
                payload=QueueItemIn(**payload),
            )

        assert status == 201
        assert isinstance(item, QueueItemOut)
        assert item.video_id == "p-Z3YrHJ1sU"
        assert item.status == JukeboxQueueItem.STATUS_PLAYING
        assert JukeboxQueueItem.objects.count() == 1
        assert proxy_request_mock.call_args_list == [
            call("DELETE", "queue"),
            call("POST", "queue", json={"videoId": "p-Z3YrHJ1sU"}),
            call("PATCH", "queue", json={"index": 0}),
            call("POST", "play"),
        ]

    def test_add_to_custom_queue_keeps_local_item_when_sync_fails(self) -> None:
        request = self.factory.post("/api/jukebox/queue")
        payload = QueueItemIn(
            video_id="p-Z3YrHJ1sU",
            title="Stereo Love (Extended Mix)",
            artist="Edward Maya & Vika Jigulina",
            thumbnail_url="https://i.ytimg.com/vi/p-Z3YrHJ1sU/hqdefault.jpg",
            duration="4:13",
        )

        with patch(
            f"{SERVICE_PATH}.proxy_request",
            return_value=(503, {"detail": "Pear API unreachable"}),
        ) as proxy_request_mock:
            status, item = add_to_custom_queue(request, payload)

        assert status == 201
        assert item.video_id == "p-Z3YrHJ1sU"
        assert item.status == JukeboxQueueItem.STATUS_QUEUED
        assert JukeboxQueueItem.objects.count() == 1
        assert proxy_request_mock.call_count == 1

    def test_push_to_pear_syncs_and_plays_selected_item(self) -> None:
        JukeboxQueueItem.objects.create(
            video_id="one",
            title="One",
            sort_order=0,
        )
        selected = JukeboxQueueItem.objects.create(
            video_id="two",
            title="Two",
            sort_order=1,
        )
        JukeboxQueueItem.objects.create(
            video_id="three",
            title="Three",
            sort_order=2,
        )

        request = self.factory.post(f"/api/jukebox/queue/{selected.id}/push")

        with patch(
            f"{SERVICE_PATH}.proxy_request",
            side_effect=[
                (204, None),
                (204, None),
                (204, None),
                (204, None),
                (204, None),
                (204, None),
            ],
        ) as proxy_request_mock:
            result = push_to_pear(request, selected.id)

        assert result == (204, None)
        assert proxy_request_mock.call_args_list == [
            call("DELETE", "queue"),
            call("POST", "queue", json={"videoId": "one"}),
            call("POST", "queue", json={"videoId": "two"}),
            call("POST", "queue", json={"videoId": "three"}),
            call("PATCH", "queue", json={"index": 1}),
            call("POST", "play"),
        ]

    def test_reconcile_marks_playing_as_played_when_player_has_no_song(
        self,
    ) -> None:
        first = JukeboxQueueItem.objects.create(
            video_id="one",
            title="One",
            status=JukeboxQueueItem.STATUS_PLAYING,
            sort_order=0,
        )
        JukeboxQueueItem.objects.create(
            video_id="two",
            title="Two",
            sort_order=1,
        )

        request = self.factory.post("/api/jukebox/queue/reconcile")

        with patch(
            f"{SERVICE_PATH}.proxy_request",
            return_value=(204, None),
        ) as proxy_request_mock:
            result = reconcile_custom_queue(request)

        first.refresh_from_db()
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[0], int)
        ):
            status, items = result
        else:
            status, items = 200, result
        assert status == 200
        assert first.status == JukeboxQueueItem.STATUS_PLAYED
        assert isinstance(items, list)
        assert [item.video_id for item in items] == ["one", "two"]
        assert proxy_request_mock.call_args_list == [call("GET", "song")]

    def test_reconcile_custom_queue_promotes_matching_remote_song(self) -> None:
        JukeboxQueueItem.objects.create(
            video_id="one",
            title="One",
            status=JukeboxQueueItem.STATUS_PLAYED,
            sort_order=0,
        )
        queued = JukeboxQueueItem.objects.create(
            video_id="two",
            title="Two",
            sort_order=1,
        )
        JukeboxQueueItem.objects.create(
            video_id="three",
            title="Three",
            sort_order=2,
        )

        request = self.factory.post("/api/jukebox/queue/reconcile")

        with patch(
            f"{SERVICE_PATH}.proxy_request",
            return_value=(200, {"videoId": "two"}),
        ) as proxy_request_mock:
            result = reconcile_custom_queue(request)

        queued.refresh_from_db()
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[0], int)
        ):
            status, items = result
        else:
            status, items = 200, result
        assert status == 200
        assert queued.status == JukeboxQueueItem.STATUS_PLAYING
        assert isinstance(items, list)
        assert [item.status for item in items] == [
            JukeboxQueueItem.STATUS_PLAYED,
            JukeboxQueueItem.STATUS_PLAYING,
            JukeboxQueueItem.STATUS_QUEUED,
        ]
        assert proxy_request_mock.call_args_list == [call("GET", "song")]
