"""Tests locaux de l'interface (sans lien public, sans GPU)."""
from __future__ import annotations

import shutil

import requests
import yaml

from . import webapp


def main():
    # 1. question piégée : reste du texte dans le YAML, jamais dans une commande
    q = 'Le "silence" ; est-il ; rm -rf ~ $(whoami) `id` une forme de langage ?'
    d = webapp.make_request(q, "foret", True, "datura", 1.0, 30, 2, "mixte")
    req = yaml.safe_load((d / "request.yaml").read_text(encoding="utf-8"))
    assert req["input"]["phrase"] == q, req["input"]["phrase"]
    print("question piégée conservée telle quelle :", req["input"]["phrase"])
    shutil.rmtree(d)
    for bad in [("x", "inconnu", False, "aucune", 1, 60, 1, "mixte"), ("x", "aucun", False, "cafe", 1, 60, 1, "mixte"),
                ("x", "aucun", False, "aucune", 1, 60, 1, "rm -rf"), ("", "aucun", False, "aucune", 1, 60, 1, "mixte")]:
        try:
            webapp.make_request(*bad)
            raise AssertionError(f"accepté à tort : {bad}")
        except ValueError as e:
            print("refusé :", e)

    # 2. serveur local avec mot de passe
    demo = webapp.build()
    user, pw = webapp.get_auth()
    demo.launch(share=False, auth=(user, pw), server_name="127.0.0.1", server_port=7861,
                allowed_paths=[str(webapp.RUNS)], prevent_thread_lock=True, quiet=True, footer_links=[])
    base = "http://127.0.0.1:7861"
    try:
        s = requests.Session()
        r = s.get(base + "/config")
        print("config sans connexion :", r.status_code)
        r = s.post(base + "/login", data={"username": user, "password": "faux"})
        print("mauvais mot de passe :", r.status_code)
        r = s.post(base + "/login", data={"username": user, "password": pw})
        print("bon mot de passe :", r.status_code)
        r = s.get(base + "/config")
        print("config après connexion :", r.status_code)
        for path in ["/etc/passwd", str(webapp.AUTH_FILE), str(webapp.ROOT / "configs" / "default.yaml")]:
            r = s.get(base + "/gradio_api/file=" + path)
            print(f"fichier hors runs/ {path} :", r.status_code)
        vids = webapp.videos()
        if vids:
            r = s.get(base + "/gradio_api/file=" + vids[0][1], stream=True)
            print("vidéo dans runs/ :", r.status_code)
        print("vidéos en galerie :", len(vids))
    finally:
        demo.close()


if __name__ == "__main__":
    main()
