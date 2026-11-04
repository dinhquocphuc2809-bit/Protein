from tools.site_acceptance_matrix import sample_status


RULE = {"site": "loom", "pages": ["https://www.loom.com/embed/*"]}


def sample(**frame):
    return {"url": "https://www.skool.com/club/about", "acquired": True,
            "frames": [{"rules": ["loom"], "host": "www.loom.com", "state": "ready",
                        "cues": 55, "first": 0, "last": 184.94, "duration": 189.066,
                        "playerButton": True, "mediaError": None, **frame}]}


def test_rejected_live_probe_never_counts_as_success():
    row = sample()
    row["acceptance"] = "Rejected: selected a preview video."
    assert sample_status(row, RULE) == "rejected"


def test_caption_success_is_not_playback_or_cross_frame_success():
    assert sample_status(sample(), RULE) == "captions-and-player-sample"
    assert sample_status(sample(duration=None, mediaError=4), RULE) == "captions-only"
    assert sample_status(sample(duration=5), RULE) == "captions-only"
    assert sample_status(sample(playerButton=False), RULE) == "captions-only"
    skool = {"site": "skool", "pages": ["https://www.skool.com/*/about"]}
    assert sample_status(sample(), skool) == "no-caption-result"


def test_access_denied_does_not_mean_no_subtitles():
    row = {"url": "https://www.loom.com/embed/test", "http_status": 403, "frames": []}
    assert sample_status(row, RULE) == "access-blocked"
