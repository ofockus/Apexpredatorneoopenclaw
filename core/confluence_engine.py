"""
core/confluence_engine.py
APEX PREDATOR NEO v666.1 – ConfluenceEngine Completo (7 Módulos)

 1. Tire Pressure           Pressão direcional do book
 2. Lead-Lag Gravitacional  Sincronia temporal de pernas
 3. Fake Momentum Filter    Detecta momentum artificial
 4. Consistência OI Spike   Volume sustentado vs ruído
 5. OI_delta/Volume Ratio   Equilíbrio bid/ask real
 6. Reversão Pós-Spike      Risco de price reversal
 7. Order Book Entropy      Anti-spoof via Shannon H

Score final: 0-100 (ponderado). Rejeita se < MIN_CONFLUENCE_SCORE
OU se houver red flag (fake momentum, spoof detectado, reversal alto).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger

from config.config import cfg


@dataclass
class ConfluenceResult:
    score: float = 0.0
    tire_pressure: float = 0.0
    lead_lag_signal: float = 0.0
    fake_momentum_flag: bool = False
    oi_spike_consistency: float = 0.0
    oi_delta_vol_ratio: float = 0.0
    reversal_risk: float = 0.0
    book_entropy: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return (
            self.score >= cfg.MIN_CONFLUENCE_SCORE
            and not self.fake_momentum_flag
            and self.reversal_risk < 0.70
            and self.book_entropy > 0.20
        )


class ConfluenceEngine:
    WEIGHTS = {
        "tire":     0.18,
        "leadlag":  0.14,
        "fake":     0.16,
        "oi_cons":  0.10,
        "oi_ratio": 0.10,
        "reversal": 0.16,
        "entropy":  0.16,
    }

    def __init__(self) -> None:
        self._vol_history: Dict[str, List[float]] = {}
        self._max_history: int = 200

    def analyze(self, triangle: Dict[str, Any], orderbooks: Dict[str, Dict], tickers: Dict[str, Dict]) -> ConfluenceResult:
        result = ConfluenceResult()
        legs = triangle.get("legs", [])
        if len(legs) < 3:
            result.details["error"] = "Triângulo incompleto (< 3 pernas)"
            return result

        try:
            result.tire_pressure = self._tire_pressure(legs, orderbooks)
            result.lead_lag_signal = self._lead_lag(legs, tickers)
            result.fake_momentum_flag = self._fake_momentum(legs, orderbooks, tickers)
            result.oi_spike_consistency = self._oi_consistency(legs, tickers)
            result.oi_delta_vol_ratio = self._oi_delta_ratio(legs, tickers)
            result.reversal_risk = self._reversal_risk(legs, tickers)
            result.book_entropy = self._book_entropy(legs, orderbooks)
            result.score = self._final_score(result)
            result.details = {
                "legs": [leg.get("symbol", "") for leg in legs],
                "weights": self.WEIGHTS,
                "module_scores": {
                    "tire": round(result.tire_pressure, 4),
                    "leadlag": round(result.lead_lag_signal, 4),
                    "fake": result.fake_momentum_flag,
                    "oi_cons": round(result.oi_spike_consistency, 4),
                    "oi_ratio": round(result.oi_delta_vol_ratio, 4),
                    "reversal": round(result.reversal_risk, 4),
                    "entropy": round(result.book_entropy, 4),
                },
            }
        except Exception as exc:
            logger.error(f"Confluência erro: {exc}")
            result.details["error"] = str(exc)
        return result

    def _tire_pressure(self, legs: List[Dict], obs: Dict[str, Dict]) -> float:
        values = []
        for leg in legs:
            ob = obs.get(leg.get("symbol", ""), {})
            bids = ob.get("bids", [])[:5]
            asks = ob.get("asks", [])[:5]
            if not bids or not asks:
                values.append(0.0)
                continue
            bid_vol = sum(q for _, q in bids)
            ask_vol = sum(q for _, q in asks)
            total = bid_vol + ask_vol
            if total <= 0:
                values.append(0.0)
                continue
            pressure = (bid_vol - ask_vol) / total
            side = leg.get("side", "buy")
            if side == "sell":
                pressure = -pressure
            values.append(pressure)
        return float(np.mean(values)) if values else 0.0

    def _lead_lag(self, legs: List[Dict], tickers: Dict[str, Dict]) -> float:
        changes = []
        for leg in legs:
            tk = tickers.get(leg.get("symbol", ""), {})
            pct = tk.get("percentage", 0) or 0
            changes.append(pct)
        if len(changes) < 3:
            return 0.0
        std = float(np.std(changes))
        if std < 0.1:
            return 0.90
        elif std < 0.5:
            return 0.50
        else:
            return -0.30

    def _fake_momentum(self, legs: List[Dict], obs: Dict[str, Dict], tickers: Dict[str, Dict]) -> bool:
        for leg in legs:
            sym = leg.get("symbol", "")
            tk = tickers.get(sym, {})
            vol = tk.get("quoteVolume", 0) or 0
            ob = obs.get(sym, {})
            bids = ob.get("bids", [])[:5]
            asks = ob.get("asks", [])[:5]
            bid_depth = sum(p * q for p, q in bids) if bids else 0
            ask_depth = sum(p * q for p, q in asks) if asks else 0
            total_depth = bid_depth + ask_depth
            if vol > 0 and total_depth > 0:
                key = sym
                hist = self._vol_history.get(key, [])
                hist.append(vol)
                if len(hist) > self._max_history:
                    hist = hist[-self._max_history:]
                self._vol_history[key] = hist
                if len(hist) >= 10:
                    avg = float(np.mean(hist[-20:]))
                    if vol > avg * 3 and total_depth < avg * 0.1:
                        return True
        return False

    def _oi_consistency(self, legs: List[Dict], tickers: Dict[str, Dict]) -> float:
        values = []
        for leg in legs:
            tk = tickers.get(leg.get("symbol", ""), {})
            vol = tk.get("quoteVolume", 0) or 0
            avg = tk.get("average", 0) or 0
            if vol > 0 and avg > 0:
                values.append(min(1.0, vol / (avg * 1000)))
            else:
                values.append(0.5)
        return float(np.mean(values)) if values else 0.5

    def _oi_delta_ratio(self, legs: List[Dict], tickers: Dict[str, Dict]) -> float:
        values = []
        for leg in legs:
            tk = tickers.get(leg.get("symbol", ""), {})
            bid_v = tk.get("bidVolume", 0) or 0
            ask_v = tk.get("askVolume", 0) or 0
            total = bid_v + ask_v
            if total > 0:
                balance = 1.0 - abs(bid_v - ask_v) / total
                values.append(balance)
            else:
                values.append(0.5)
        return float(np.mean(values)) if values else 0.5

    def _reversal_risk(self, legs: List[Dict], tickers: Dict[str, Dict]) -> float:
        vals = []
        for leg in legs:
            tk = tickers.get(leg.get("symbol", ""), {})
            hi = tk.get("high", 0) or 0
            lo = tk.get("low", 0) or 0
            last = tk.get("last", 0) or 0
            if hi <= lo or last <= 0:
                vals.append(0.5)
                continue
            rng = (hi - lo) / lo * 100
            pos = (last - lo) / (hi - lo)
            if rng > 5 and (pos > 0.85 or pos < 0.15):
                vals.append(0.80)
            elif rng > 3:
                vals.append(0.40)
            else:
                vals.append(0.15)
        return float(np.mean(vals)) if vals else 0.5

    def _book_entropy(self, legs: List[Dict], obs: Dict[str, Dict]) -> float:
        vals = []
        for leg in legs:
            ob = obs.get(leg.get("symbol", ""), {})
            for side in ("bids", "asks"):
                orders = ob.get(side, [])[:10]
                if len(orders) < 3:
                    vals.append(0.0)
                    continue
                vols = [q for _, q in orders if q > 0]
                total = sum(vols)
                if total <= 0 or len(vols) < 2:
                    vals.append(0.0)
                    continue
                probs = [v / total for v in vols]
                ent = -sum(p * math.log2(p) for p in probs if p > 0)
                max_ent = math.log2(len(probs))
                vals.append(ent / max_ent if max_ent > 0 else 0)
        return float(np.mean(vals)) if vals else 0.5

    def _final_score(self, r: ConfluenceResult) -> float:
        s = {
            "tire":     (r.tire_pressure + 1) / 2,
            "leadlag":  (r.lead_lag_signal + 1) / 2,
            "fake":     0.0 if r.fake_momentum_flag else 1.0,
            "oi_cons":  r.oi_spike_consistency,
            "oi_ratio": r.oi_delta_vol_ratio,
            "reversal": 1.0 - r.reversal_risk,
            "entropy":  r.book_entropy,
        }
        weighted = sum(s[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return max(0.0, min(100.0, weighted * 100))


confluence = ConfluenceEngine()
