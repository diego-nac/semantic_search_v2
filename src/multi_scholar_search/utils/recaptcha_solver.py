"""reCAPTCHA audio solver using DrissionPage + ffmpeg + OpenAI Whisper."""
from __future__ import annotations

import os
import random
import subprocess
import tempfile
import time
import urllib.request
from typing import Optional

_whisper_model = None

TIMEOUT_STANDARD = 7
TIMEOUT_SHORT = 1
TIMEOUT_DETECTION = 0.05


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        import logging
        logging.getLogger("mss").info("[recaptcha] Loading Whisper model (base.en)...")
        _whisper_model = whisper.load_model("base.en")
    return _whisper_model


def _mp3_to_wav(mp3_path: str, wav_path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", mp3_path, wav_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


class DrissionRecaptchaSolver:
    """Solve reCAPTCHA v2 via audio challenge using DrissionPage."""

    def __init__(self, driver) -> None:
        self.driver = driver

    def solve(self) -> None:
        """Attempt to solve reCAPTCHA. Raises on failure."""
        import logging
        log = logging.getLogger("mss.recaptcha")

        # Step 1: click the checkbox
        self.driver.wait.ele_displayed("@title=reCAPTCHA", timeout=TIMEOUT_STANDARD)
        time.sleep(0.1)
        checkbox_iframe = self.driver("@title=reCAPTCHA")
        checkbox_iframe.wait.ele_displayed(".rc-anchor-content", timeout=TIMEOUT_STANDARD)
        checkbox_iframe(".rc-anchor-content", timeout=TIMEOUT_SHORT).click()
        time.sleep(0.5)

        if self._is_solved():
            log.debug("[recaptcha] Solved by checkbox click")
            return

        # Step 2: switch to challenge iframe → click Audio
        challenge_iframe = self.driver(
            "xpath://iframe[contains(@title, 'recaptcha challenge')]"
        )
        challenge_iframe.wait.ele_displayed(
            "#recaptcha-audio-button", timeout=TIMEOUT_STANDARD
        )
        challenge_iframe("#recaptcha-audio-button", timeout=TIMEOUT_SHORT).click()
        time.sleep(1.0)

        if self._is_detected():
            raise RuntimeError("reCAPTCHA: bot detected — try again later")

        # Step 3: get audio src
        challenge_iframe.wait.ele_displayed("#audio-source", timeout=TIMEOUT_STANDARD)
        src = challenge_iframe("#audio-source").attrs["src"]
        if not src:
            raise RuntimeError("reCAPTCHA: could not get audio src")
        log.debug("[recaptcha] Audio src: %s", src[:80])

        # Step 4: transcribe and submit
        text = self._process_audio(src)
        log.info("[recaptcha] Submitting transcription: %r", text)
        challenge_iframe("#audio-response").input(text.lower())
        time.sleep(0.3)
        challenge_iframe("#recaptcha-verify-button").click()
        time.sleep(1.0)

        if not self._is_solved():
            raise RuntimeError("reCAPTCHA: audio response rejected")

        log.info("[recaptcha] Solved via audio challenge")

    def _process_audio(self, url: str) -> str:
        tmp = tempfile.gettempdir()
        uid = random.randrange(1, 10000)
        mp3 = os.path.join(tmp, f"captcha_{uid}.mp3")
        wav = os.path.join(tmp, f"captcha_{uid}.wav")
        try:
            urllib.request.urlretrieve(url, mp3)
            _mp3_to_wav(mp3, wav)
            model = _get_whisper()
            result = model.transcribe(wav, language="en", fp16=False)
            return result["text"].strip()
        finally:
            for path in (mp3, wav):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass

    def _is_solved(self) -> bool:
        try:
            return "style" in self.driver.ele(
                ".recaptcha-checkbox-checkmark", timeout=TIMEOUT_SHORT
            ).attrs
        except Exception:
            return False

    def _is_detected(self) -> bool:
        try:
            return self.driver.ele(
                "Try again later", timeout=TIMEOUT_DETECTION
            ).states.is_displayed
        except Exception:
            return False

    def get_token(self) -> Optional[str]:
        try:
            return self.driver.ele("#recaptcha-token").attrs["value"]
        except Exception:
            return None
