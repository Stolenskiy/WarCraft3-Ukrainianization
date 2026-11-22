"""Голоси спільноти: автори, вибір, публікація власного голосу, прослуховування рядка."""
from __future__ import annotations

from .registry import Ctx, File, route


@route("GET", "/api/voices")
def voices(c: Ctx):
    return c.svc.voices_json()


@route("GET", "/audio/voice/<author>/<rel:path>")
def voice_audio(c: Ctx):
    return File(c.svc.voice_audio(c.params["author"], c.params["rel"]), "audio/wav")


@route("POST", "/api/voices/choice")
def voices_choice(c: Ctx):
    return c.svc.set_voice_choice(c.data)


@route("POST", "/api/voices/publish")
def voices_publish(c: Ctx):
    d = c.data
    return c.svc.publish_voice(d.get("nickname"), d.get("consent") is True)
