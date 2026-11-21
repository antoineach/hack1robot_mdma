"""Chargement de Gemma 3 + J-lens, lecture J-lens en fp32 et directions de drogue."""
from __future__ import annotations

import math
import unicodedata

import torch

from . import common  # noqa: F401  (fixe HF_HUB_CACHE)
from .stopwords import ALL as STOPWORDS


def load_model(cfg: dict, device: str = "cuda"):
    import transformers

    name = cfg["model"]
    tok = transformers.AutoTokenizer.from_pretrained(name)
    # Gemma 3 12B-it est un checkpoint multimodal ; on charge la classe complète
    # (jamais trust_remote_code) et jlens trouve le décodeur texte.
    try:
        from transformers import Gemma3ForConditionalGeneration as Cls
    except ImportError:  # pragma: no cover
        Cls = transformers.AutoModelForCausalLM
    model = Cls.from_pretrained(name, dtype=torch.bfloat16, device_map=device)
    model.eval()
    return model, tok


def load_lens(cfg: dict):
    import jlens

    return jlens.JacobianLens.from_pretrained(cfg["lens"]["repo"], filename=cfg["lens"]["file"])


class Reader:
    """Lecture J-lens : logits_l = unembed(h_l @ J[l].T), en fp32."""

    def __init__(self, model, tok, lens, cfg: dict, device: str = "cuda"):
        import jlens

        self.cfg = cfg
        self.tok = tok
        self.device = device
        self.lm = jlens.from_hf(model, tok, force_bos=False)
        self.n_layers = self.lm.n_layers
        self.d_model = self.lm.d_model
        lo, hi = cfg["readout"]["band"]
        band = [l for l in lens.source_layers if lo * self.n_layers <= l <= hi * self.n_layers]
        self.band = band
        self.lens = lens
        self.J = torch.stack([lens.jacobians[l] for l in band]).to(device, torch.float32)  # [L,d,d]
        self.norm = self.lm._final_norm
        self.W_U = self.lm._lm_head.weight.detach().to(torch.float32)  # [V,d] fp32
        self.softcap = self.lm._logit_softcap
        self.top_k = cfg["readout"]["top_k"]
        self.word_mask = self._build_word_mask(cfg)
        lw = cfg["readout"].get("layer_weights")
        self.layer_weights = torch.tensor(lw if lw else [1.0] * len(band), dtype=torch.float32)

    # --- vocabulaire -----------------------------------------------------
    def _build_word_mask(self, cfg) -> torch.Tensor:
        min_len = cfg["readout"]["min_len"]
        stop = STOPWORDS | set(cfg["readout"].get("stopwords_extra") or [])
        V = self.W_U.shape[0]
        mask = torch.zeros(V, dtype=torch.bool)
        self.word_of = {}
        pieces = self.tok.convert_ids_to_tokens(list(range(min(V, len(self.tok)))))
        for i, p in enumerate(pieces):
            if not p or not p.startswith("▁"):
                continue
            w = p[1:]
            if len(w) < min_len or not all(unicodedata.category(c).startswith("L") for c in w):
                continue
            lw = w.lower()
            if lw in stop:
                continue
            mask[i] = True
            self.word_of[i] = lw
        return mask.to(self.device)

    # --- lecture ---------------------------------------------------------
    def unembed(self, x: torch.Tensor) -> torch.Tensor:
        x = self.norm(x.float()).float()
        logits = x @ self.W_U.T
        if self.softcap is not None:
            logits = self.softcap * torch.tanh(logits / self.softcap)
        return logits

    @torch.no_grad()
    def read(self, H: torch.Tensor):
        """H : [L_band, d] résidus (une position). Renvoie par couche la liste
        [(mot, prob)] filtrée et l'entropie de la lecture."""
        T = torch.einsum("lij,lj->li", self.J, H.float())  # J @ h
        probs = torch.softmax(self.unembed(T), dim=-1)  # [L,V]
        ent = -(probs * torch.log(probs.clamp_min(1e-12))).sum(-1)
        if self.cfg["readout"].get("filter_before_topk"):
            p = probs.masked_fill(~self.word_mask, 0.0)
        else:
            p = probs
        val, idx = p.topk(self.top_k, dim=-1)
        val, idx = val.cpu().tolist(), idx.cpu().tolist()
        out = []
        for li in range(len(self.band)):
            agg: dict[str, float] = {}
            for v, i in zip(val[li], idx[li]):
                w = self.word_of.get(i)
                if w is not None:
                    agg[w] = agg.get(w, 0.0) + v
            out.append(sorted(([w, round(s, 6)] for w, s in agg.items()), key=lambda x: -x[1]))
        return out, ent.cpu().tolist()

    # --- drogue ----------------------------------------------------------
    def gain(self) -> torch.Tensor:
        w = self.norm.weight.detach().float()
        # Gemma3RMSNorm multiplie par (1 + weight)
        return 1.0 + w

    def direction(self, word: str, layer: int, log=print) -> torch.Tensor:
        ids = self.word_token_ids(word, log)
        J = self.lens.jacobians[layer].to(self.device, torch.float32)
        g = self.gain()
        vs = []
        for t in ids:
            v = J.T @ (g * self.W_U[t])
            vs.append(v / v.norm())
        v = torch.stack(vs).mean(0)
        return v / v.norm()

    def word_token_ids(self, word: str, log=print) -> list[int]:
        for cand in ("▁" + word, "▁" + word.lower(), "▁" + word.capitalize()):
            tid = self.tok.convert_tokens_to_ids(cand)
            if isinstance(tid, int) and tid != self.tok.unk_token_id:
                return [tid]
        ids = self.tok.encode(" " + word, add_special_tokens=False)
        log(f"ATTENTION : le mot-drogue '{word}' fait {len(ids)} tokens {self.tok.convert_ids_to_tokens(ids)} ; moyenne des directions")
        return ids


def drug_alpha(d: dict, step: int) -> float:
    a = float(d.get("alpha", 0.0))
    prof = d.get("profile", "constant")
    start, end = d.get("start", 0), d.get("end", None)
    period = d.get("period", 40)
    if step < start:
        return 0.0
    if prof == "constant":
        return a
    if prof == "ramp":
        if end is None or end <= start:
            return a
        return a * min(1.0, (step - start) / (end - start))
    if prof == "pulse":
        return a if ((step - start) // max(1, period // 2)) % 2 == 0 else 0.0
    if prof == "sine":
        return a * 0.5 * (1 - math.cos(2 * math.pi * (step - start) / max(1, period)))
    raise ValueError(f"profil de drogue inconnu : {prof}")
