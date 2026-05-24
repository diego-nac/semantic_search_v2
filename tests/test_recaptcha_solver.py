import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from multi_scholar_search.utils.recaptcha_solver import (
    DrissionRecaptchaSolver,
    _mp3_to_wav,
)


# -- helpers --

def make_solver(driver=None):
    return DrissionRecaptchaSolver(driver or MagicMock())


# -- _mp3_to_wav --

def test_mp3_to_wav_calls_ffmpeg():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _mp3_to_wav("/tmp/in.mp3", "/tmp/out.wav")
        args = mock_run.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert "/tmp/in.mp3" in args
        assert "/tmp/out.wav" in args


def test_mp3_to_wav_raises_on_ffmpeg_failure():
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")):
        with pytest.raises(subprocess.CalledProcessError):
            _mp3_to_wav("/tmp/in.mp3", "/tmp/out.wav")


# -- _is_solved --

def test_is_solved_true_when_checkmark_has_style():
    driver = MagicMock()
    driver.ele.return_value.attrs = {"style": "display:block"}
    solver = make_solver(driver)
    assert solver._is_solved() is True


def test_is_solved_false_when_no_style():
    driver = MagicMock()
    driver.ele.return_value.attrs = {}
    solver = make_solver(driver)
    assert solver._is_solved() is False


def test_is_solved_false_on_exception():
    driver = MagicMock()
    driver.ele.side_effect = Exception("not found")
    solver = make_solver(driver)
    assert solver._is_solved() is False


# -- _is_detected --

def test_is_detected_true_when_displayed():
    driver = MagicMock()
    driver.ele.return_value.states.is_displayed = True
    solver = make_solver(driver)
    assert solver._is_detected() is True


def test_is_detected_false_on_exception():
    driver = MagicMock()
    driver.ele.side_effect = Exception("not found")
    solver = make_solver(driver)
    assert solver._is_detected() is False


# -- get_token --

def test_get_token_returns_value():
    driver = MagicMock()
    driver.ele.return_value.attrs = {"value": "token-abc123"}
    solver = make_solver(driver)
    assert solver.get_token() == "token-abc123"


def test_get_token_returns_none_on_exception():
    driver = MagicMock()
    driver.ele.side_effect = Exception("not found")
    solver = make_solver(driver)
    assert solver.get_token() is None


# -- _process_audio --

def test_process_audio_cleans_up_temp_files():
    tmp = tempfile.gettempdir()
    solver = make_solver()

    with (
        patch("urllib.request.urlretrieve"),
        patch("multi_scholar_search.utils.recaptcha_solver._mp3_to_wav"),
        patch("multi_scholar_search.utils.recaptcha_solver._get_whisper") as mock_w,
    ):
        mock_w.return_value.transcribe.return_value = {"text": "answer text"}
        result = solver._process_audio("http://example.com/audio.mp3")

    assert result == "answer text"


def test_process_audio_returns_stripped_text():
    solver = make_solver()
    with (
        patch("urllib.request.urlretrieve"),
        patch("multi_scholar_search.utils.recaptcha_solver._mp3_to_wav"),
        patch("multi_scholar_search.utils.recaptcha_solver._get_whisper") as mock_w,
    ):
        mock_w.return_value.transcribe.return_value = {"text": "  hello world  "}
        result = solver._process_audio("http://example.com/audio.mp3")

    assert result == "hello world"
