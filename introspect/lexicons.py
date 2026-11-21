"""Lexiques : Lancaster (sensorimoteur), NRC VAD (anglais + français), Brysbaert (concrétude)."""
from __future__ import annotations

import csv
import functools
import unicodedata

from .common import ROOT

LEX = ROOT / "weights" / "lexicons"


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


@functools.lru_cache(None)
def nrc_en() -> dict[str, tuple[float, float, float]]:
    out = {}
    p = LEX / "nrc" / "NRC-VAD-Lexicon" / "NRC-VAD-Lexicon.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) == 4:
                try:
                    out[parts[0].lower()] = tuple(float(x) for x in parts[1:])
                except ValueError:
                    pass
    return out


@functools.lru_cache(None)
def nrc_fr() -> dict[str, tuple[tuple[float, float, float], str]]:
    """mot français -> ((v, a, d), mot anglais)."""
    out = {}
    p = LEX / "nrc" / "NRC-VAD-Lexicon" / "OneFilePerLanguage" / "French-NRC-VAD-Lexicon.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) == 5:
                try:
                    vad = tuple(float(x) for x in parts[1:4])
                except ValueError:
                    continue
                fr = parts[4].strip().lower()
                if fr and " " not in fr and fr not in out:
                    out[fr] = (vad, parts[0].lower())
    return out


@functools.lru_cache(None)
def lancaster() -> dict[str, dict[str, float]]:
    out = {}
    p = LEX / "lancaster.csv"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out[r["Word"].lower()] = {
                        "auditory": float(r["Auditory.mean"]) / 5, "visual": float(r["Visual.mean"]) / 5,
                        "haptic": float(r["Haptic.mean"]) / 5, "olfactory": float(r["Olfactory.mean"]) / 5,
                        "gustatory": float(r["Gustatory.mean"]) / 5, "interoceptive": float(r["Interoceptive.mean"]) / 5,
                    }
                except (KeyError, ValueError):
                    pass
    return out


@functools.lru_cache(None)
def concreteness() -> dict[str, float]:
    out = {}
    p = LEX / "Concreteness_ratings_Brysbaert_et_al_BRM.txt"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) > 2 and parts[1] == "0":
                try:
                    out[parts[0].lower()] = (float(parts[2]) - 1) / 4
                except ValueError:
                    pass
    return out


@functools.lru_cache(None)
def english_words() -> frozenset:
    return frozenset(nrc_en()) | frozenset(concreteness()) | frozenset(lancaster())


@functools.lru_cache(None)
def french_words() -> frozenset:
    return frozenset(nrc_fr())


def lang_of(word: str) -> str:
    """Détection de langue simple : 'fr' ou 'en'."""
    w = word.lower()
    if w != strip_accents(w):
        return "fr"
    in_en, in_fr = w in english_words(), w in french_words()
    if in_en and not in_fr:
        return "en"
    if in_fr and not in_en:
        return "fr"
    if in_en and in_fr:
        return "en" if w in lancaster() else "fr"
    return "fr"
