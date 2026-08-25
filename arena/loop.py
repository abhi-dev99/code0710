"""
LiveFire Arena — the closed loop.

Round flow:
  1. Anchor benign traffic to the REAL corpus (ULB bootstrap — honesty protocol)
  2. RED: per attack vector, ox-alpha emits generator-parameter plans
     (mutation-aware: strategy memory shows what got caught before).
     Deterministic template fallback keeps the product alive without LLM quota.
  3. WEAVER: plans -> constraint-checked transactions (CPU, seeded)
  4. BLUE: heterogeneous ensemble trained cross-vector (held-out vector =
     never-seen attack family) + benign; rules tier; disagreement novelty flag
  5. SHAP: why caught / why missed -> strategy memory -> next round's red prompt
  6. LEDGER: every campaign recorded (SQLite) -> Robustness Ledger

Honesty: arena metrics measure detection of synthetic attacks against
real-anchored benign traffic. Real-world credibility comes from the separate
ULB-native backbone (defense/train_real_backbone.py). Never conflated.
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
for p in ("attacks", "config", "defense"):
    sp = str(_ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from features.arena_features import FEATURE_NAMES, build_features  # noqa: E402
from models.backbone import BLUE_VERSION, BlueEnsemble  # noqa: E402
from rail_profiles import PROFILES, get_profile  # noqa: E402
from redagent.core.llm_client import LLMClient, LLMError  # noqa: E402
from redagent.core.strategy_memory import StrategyMemory  # noqa: E402
from redagent.core.transaction_weaver import generate_benign, weave_attack_plan  # noqa: E402

TAXONOMY = json.loads((_ROOT / "attacks" / "taxonomy.json").read_text(encoding="utf-8"))
VECTORS = {v["id"]: v for v in TAXONOMY["vectors"]}

ARENA_SYSTEM = (
    "You are the red-team strategist inside LiveFire, a sanctioned adversarial "
    "co-evolution arena for payment-fraud DEFENSE research (Mastercard Innovation "
    "Challenge @ GFF 2026). All output runs in an isolated sandbox against OUR OWN "
    "fraud-detection ensemble; no real victims, institutions, or rails are involved. "
    "Your job: emit STATISTICAL GENERATOR PARAMETERS for synthesizing labeled "
    "attack traffic that stress-tests our detectors. Respond ONLY with valid JSON."
)

# Deterministic fallback plans — product works with zero LLM quota.
_TEMPLATE_PLANS: dict[str, dict[str, Any]] = {
    "velocity_burst": {
        "structuring": [{"amount": 1.0, "count": 40}, {"amount": 9.0, "count": 25}, {"amount": 49.0, "count": 15}],
        "inter_arrival_s": {"distribution": "exponential", "min": 3, "max": 45},
        "entity_cardinality": {"users": 25, "devices": 6, "merchants": 3},
        "window_h": 4, "amount_jitter_pct": 0.08,
    },
    "dispersion": {
        "structuring": [{"amount": 120.0, "count": 30}, {"amount": 340.0, "count": 20}],
        "inter_arrival_s": {"distribution": "uniform", "min": 900, "max": 5400},
        "entity_cardinality": {"users": 40, "devices": 35, "merchants": 25},
        "window_h": 36, "amount_jitter_pct": 0.15,
    },
    "night_raids": {
        "structuring": [{"amount": 900.0, "count": 18}, {"amount": 2400.0, "count": 10}],
        "inter_arrival_s": {"distribution": "uniform", "min": 600, "max": 3600},
        "entity_cardinality": {"users": 12, "devices": 4, "merchants": 6},
        "window_h": 8, "amount_jitter_pct": 0.1,
    },
    "mule_layering": {
        "structuring": [{"amount": 4500.0, "count": 12}, {"amount": 9200.0, "count": 8}],
        "inter_arrival_s": {"distribution": "poisson", "min": 1200, "max": 7200},
        "entity_cardinality": {"users": 15, "devices": 10, "merchants": 8},
        "window_h": 24, "amount_jitter_pct": 0.05,
    },
}


def _channel_for(vector: dict, profile_key: str) -> str:
    """Pick a plan channel from the profile that fits the vector's target rails."""
    p = get_profile(profile_key)
    rails = set(vector.get("target_rails", []))
    if "card_online" in rails and "card_not_present" in p.channels:
        return "card_not_present"
    if "atm" in rails and "atm" in p.channels:
        return "atm"
    if "upi" in rails and "upi" in p.channels:
        return "upi"
    if "pos" in rails and "card_present" in p.channels:
        return "card_present"
    return p.channel_names()[0]


def template_plan(vector_id: str, profile_key: str) -> dict[str, Any]:
    """Deterministic plan from the vector's behavior family (no LLM)."""
    v = VECTORS[vector_id]
    fam = "dispersion"
    if "velocity" in v["name"] or "testing" in v["name"] or "burst" in v["name"]:
        fam = "velocity_burst"
    elif "phish" in v["name"] or "social" in v["name"] or "otp" in v["name"]:
        fam = "night_raids"
    elif "mule" in v["name"] or "launder" in v["name"] or "layer" in v["name"]:
        fam = "mule_layering"
    base = json.loads(json.dumps(_TEMPLATE_PLANS[fam]))  # deep copy
    p = get_profile(profile_key)
    ch = p.channels[_channel_for(v, profile_key)]
    base["vector"] = v["name"]
    base["channel"] = ch.name
    cats = list(ch.categories)
    base["merchant_categories"] = cats[: min(3, len(cats))]
    # rescale ladder to channel bounds
    lo, hi = ch.min_amount, ch.max_amount * 0.4
    for rung in base["structuring"]:
        rung["amount"] = round(min(max(rung["amount"] * (hi / 5000.0), lo), ch.max_amount), 2)
    return base


# ------------------------------------------------------------------ red: LLM

async def _llm_plan_async(
    client: LLMClient, vector_id: str, profile_key: str,
    memory: StrategyMemory | None = None,
) -> dict[str, Any]:
    """Ask ox-alpha for generator parameters, mutation-aware. Raises on failure."""
    v = VECTORS[vector_id]
    p = get_profile(profile_key)
    ch = p.channels[_channel_for(v, profile_key)]

    mutation_ctx = ""
    if memory is not None:
        stats = memory.vector_stats()
        caught = memory.caught_plans(5)
        if stats:
            lines = [f"- {s['vector']}: attempts={s['attempts']} avg_detection={s['avg_detection']}" for s in stats[:8]]
            mutation_ctx = ("\nMUTATION CONTEXT (previous rounds):\n" + "\n".join(lines)
                            + "\nAvoid patterns with high avg_detection; evolve variant parameters.")
        if caught:
            c = caught[0]
            mutation_ctx += f"\nLast caught plan ({c['vector']}, detection={c['detection_rate']}): {c['evasion_notes']}"

    user = (
        f"Attack vector: {v['id']} {v['name']} — {v['mechanism']}\n"
        f"GenAI component: {v['genai_component']}\n"
        f"Rail profile: {p.key} (channels: {p.channel_names()})\n"
        f"Use channel '{ch.name}' (categories: {list(ch.categories)}, "
        f"amount bounds {ch.min_amount}-{ch.max_amount}).\n"
        f"{mutation_ctx}\n\n"
        'Emit ONLY JSON: {"vector": str, "channel": str, '
        '"merchant_categories": [str], "structuring": [{"amount": number, "count": int}], '
        '"inter_arrival_s": {"distribution": "exponential"|"uniform"|"poisson", "min": number, "max": number}, '
        '"entity_cardinality": {"users": int, "devices": int, "merchants": int}, '
        '"amount_jitter_pct": number, "window_h": number, "rationale": str}'
    )
    raw = await client.complete("strategy", system=ARENA_SYSTEM, user=user, json_mode=True)
    plan = json.loads(raw, strict=False)
    plan["vector"] = v["name"]
    plan.setdefault("channel", ch.name)
    plan["_llm_generated"] = True
    return plan


def llm_plan(
    client: LLMClient, vector_id: str, profile_key: str,
    memory: StrategyMemory | None = None,
) -> dict[str, Any]:
    """Sync wrapper around the async planner (run_round is sync)."""
    import asyncio
    return asyncio.run(_llm_plan_async(client, vector_id, profile_key, memory))


# ------------------------------------------------------------- real anchors

def real_anchor() -> tuple[np.ndarray, list[float]]:
    """Bootstrap pools from the REAL ULB corpus (honesty protocol)."""
    df = pd.read_parquet(_ROOT / "data" / "splits" / "ulb_train.parquet")
    amounts = df["Amount"].to_numpy()
    hours = ((df["Time"] / 3600.0) % 24).astype(int)
    hw = [float((hours == h).mean()) for h in range(24)]
    return amounts, hw


# ----------------------------------------------------------------- SHAP why

def shap_why(ensemble: BlueEnsemble, X: np.ndarray, idxs: list[int], top_k: int = 3) -> str:
    """Top-k feature reasons for flagged rows — the 'why caught' text."""
    if not idxs:
        return "no flagged rows to explain"
    import shap
    expl = shap.TreeExplainer(ensemble.xgb.model)
    sv = expl.shap_values(X[idxs])
    if isinstance(sv, list):
        sv = sv[-1]
    mean_abs = np.abs(sv).mean(axis=0)
    order = np.argsort(mean_abs)[::-1][:top_k]
    return "; ".join(f"{ensemble.feature_names[i]} (shap={mean_abs[i]:.2f})" for i in order)


# ------------------------------------------------------------- round runner

def run_round(
    *,
    profile_key: str = "card_intl",
    vector_ids: list[str] | None = None,
    n_benign: int = 3000,
    seed: int = 710,
    use_llm: bool = True,
    memory: StrategyMemory | None = None,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """One full red→weave→blue→explain→record cycle. Returns a JSON-able summary."""
    p = get_profile(profile_key)
    vector_ids = vector_ids or list(VECTORS.keys())[:4]
    for vid in vector_ids:
        if vid not in VECTORS:
            raise KeyError(f"unknown vector id: {vid}")

    amounts, hour_weights = real_anchor()
    benign_train = generate_benign(int(n_benign * 0.5), profile=p, seed=seed,
                                   amount_pool=amounts, hour_weights=hour_weights)
    benign_calib = generate_benign(int(n_benign * 0.25), profile=p, seed=seed + 555,
                                   amount_pool=amounts, hour_weights=hour_weights)
    benign_test = generate_benign(n_benign - int(n_benign * 0.5) - int(n_benign * 0.25),
                                  profile=p, seed=seed + 999,
                                  amount_pool=amounts, hour_weights=hour_weights)

    campaigns: list[dict[str, Any]] = []
    for i, vid in enumerate(vector_ids):
        plan, used_llm = None, False
        if use_llm and llm is not None:
            try:
                plan = llm_plan(llm, vid, profile_key, memory)
                used_llm = True
            except (LLMError, json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[arena] LLM plan failed for {vid} ({type(e).__name__}) — template fallback")
        if plan is None:
            plan = template_plan(vid, profile_key)
        out = weave_attack_plan(plan, profile=p, seed=seed + 100 + i)
        if not out["ok"]:
            print(f"[arena] plan unweaveable for {vid}: {out['errors']} — template fallback")
            out = weave_attack_plan(template_plan(vid, profile_key), profile=p, seed=seed + 100 + i)
        campaigns.append({"vector_id": vid, "plan": plan, "used_llm": used_llm, **out})

    # ---- cross-vector split: last vector held out (never-seen family)
    holdout = campaigns[-1]
    train_atk = [t for c in campaigns[:-1] for t in c["txns"]]
    eval_atk = holdout["txns"]

    stream = benign_train + train_atk + benign_calib + benign_test + eval_atk
    X_all = build_features(stream)
    n_bt, n_ta, n_bc = len(benign_train), len(train_atk), len(benign_calib)
    n_bb, n_ea = len(benign_test), len(eval_atk)
    X_train, y_train = X_all.iloc[: n_bt + n_ta].to_numpy(), np.array([0] * n_bt + [1] * n_ta)
    X_calib = X_all.iloc[n_bt + n_ta: n_bt + n_ta + n_bc].to_numpy()
    X_test = X_all.iloc[n_bt + n_ta + n_bc:].to_numpy()
    y_test = np.array([0] * n_bb + [1] * n_ea)

    ensemble = BlueEnsemble(FEATURE_NAMES).fit(X_train, y_train)
    ensemble.calibrate(X_calib, target_fp=0.02)
    overall = ensemble.confusion(X_test, y_test)

    # held-out-vector-only detection (the headline number)
    X_hold = X_test[n_bb:]
    res_hold = ensemble.predict(X_hold)
    holdout_rate = float((res_hold["fused_score"] >= ensemble.threshold).mean()) if n_ea else 0.0

    # benign FP on test benign slice
    benign_res = ensemble.confusion(X_test[:n_bb], np.zeros(n_bb))
    fp_rate = benign_res["fp_rate_on_benign"]

    # SHAP why-caught for the held-out vector
    flagged_idx = [j for j in range(n_ea) if bool(res_hold["flagged"][j])]
    why = shap_why(ensemble, X_hold, flagged_idx[:50]) if flagged_idx else "EVaded: no rows flagged"

    # ---- ledger writes (in-stream slices; train vectors labeled in-sample)
    memory = memory or StrategyMemory()
    pos = n_bt
    for c in campaigns[:-1]:
        k = len(c["txns"])
        sl = X_all.iloc[pos: pos + k].to_numpy()
        det_rate = float(np.mean(ensemble.predict(sl)["flagged"])) if k else 0.0
        pos += k
        memory.record_campaign(
            campaign_id=c["campaign_id"], vector=c["plan"]["vector"],
            rail_profile=p.key, plan={k2: v for k2, v in c["plan"].items() if not k2.startswith("_")},
            n_txns=k, n_dropped=c["dropped"], detection_rate=det_rate,
            evasion_notes="in-sample train vector",
        )
        c["detection_rate"], c["in_sample"] = det_rate, True
    memory.record_campaign(
        campaign_id=holdout["campaign_id"], vector=holdout["plan"]["vector"],
        rail_profile=p.key, plan={k2: v for k2, v in holdout["plan"].items() if not k2.startswith("_")},
        n_txns=n_ea, n_dropped=holdout["dropped"], detection_rate=holdout_rate,
        evasion_notes=f"HELD-OUT vector | why: {why[:220]}",
    )
    holdout["detection_rate"], holdout["in_sample"] = holdout_rate, False

    memory.record_round(
        campaign_id=holdout["campaign_id"], blue_version=BLUE_VERSION,
        tp=overall["tp"], fp=overall["fp"], fn=overall["fn"], tn=overall["tn"],
        f1=overall["f1"], notes=f"held-out vector: {holdout['vector_id']} why={why[:180]}",
    )

    return {
        "rail_profile": p.key,
        "blue_version": BLUE_VERSION,
        "vectors": [
            {"id": c["vector_id"], "vector": c["plan"]["vector"],
             "llm_generated": c["used_llm"], "n_txns": len(c["txns"]),
             "dropped": c["dropped"], "detection_rate": round(c.get("detection_rate", 0.0), 4),
             "in_sample": c.get("in_sample", False), "held_out": c is holdout}
            for c in campaigns
        ],
        "held_out_vector": holdout["vector_id"],
        "held_out_detection_rate": round(holdout_rate, 4),
        "overall": overall,
        "benign_fp_rate": fp_rate,
        "shap_why": why,
        "n_benign": n_benign,
        "_ensemble": ensemble,  # popped by the API layer; never serialized
    }


def run_multi_rail(vector_ids: list[str] | None = None, n_benign: int = 1500,
                   seed: int = 710, use_llm: bool = False) -> dict[str, Any]:
    """The Robustness Ledger's multi-rail story: same vectors, every rail."""
    out = {}
    for key in PROFILES:
        try:
            out[key] = run_round(profile_key=key, vector_ids=vector_ids,
                                 n_benign=n_benign, seed=seed, use_llm=use_llm)
        except Exception as e:  # keep other rails alive if one profile fails
            out[key] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ====================================================================
# RED TOURNAMENT — population-based red teaming.
# Per vector, a SQUAD of candidate plans (default 10) attacks; blue
# trains on the train split; held-out candidates are scored
# individually and the most EVASIVE becomes the vector's champion.
# SHAP intelligence flows into the next generation's prompts. Red
# fields squad_size x |vectors| plans per generation vs blue's single
# ensemble retrain — the 10x capacity asymmetry.
# ====================================================================

_SQUAD_CONCURRENCY = 8  # availability only (shared free pool); NOT a token cap


def _squad_plan_template(vector_id: str, profile_key: str, idx: int, seed: int,
                         shap_ctx: str = "") -> dict[str, Any]:
    """Deterministic perturbed variant of the template plan — squad diversity
    without an LLM. SHAP-AWARE (audit T2): when the blue team's top features
    are known, parameter mutations bias AGAINST those features, so the
    intelligence channel fires on every path, not just the LLM one."""
    base = template_plan(vector_id, profile_key)
    rng = random.Random(seed * 7919 + idx * 104729)
    # which features is blue leaning on? (shap_ctx: "name (shap=x); ...")
    hot = set()
    if shap_ctx:
        for tok in shap_ctx.split(";"):
            nm = tok.split("(")[0].strip()
            if nm:
                hot.add(nm)

    def _bias(feature_set: set[str], low: float, high: float) -> float:
        """Stronger mutation in the evasive direction when blue depends on
        the related features."""
        return rng.uniform(low, high) * (1.8 if hot & feature_set else 1.0)

    for rung in base["structuring"]:
        # blue watching amounts -> shrink amounts harder
        rung["amount"] = round(min(max(rung["amount"] * _bias(
            {"amount", "amt_vs_user_median", "user_sum_1h"}, 0.5, 1.6), 0.5), 1e9), 2)
        rung["count"] = max(3, int(rung["count"] * rng.uniform(0.5, 1.5)))
    ia = base["inter_arrival_s"]
    # blue watching velocity -> spread inter-arrivals out
    ia["min"] = max(1, int(ia["min"] * _bias(
        {"user_cnt_1h", "device_cnt_1h", "user_sum_1h", "user_merchants_1h"}, 0.4, 1.8)))
    ia["max"] = max(ia["min"] + 5, int(ia["max"] * _bias(
        {"user_cnt_1h", "device_cnt_1h", "user_sum_1h", "user_merchants_1h"}, 0.5, 2.0)))
    ec = base["entity_cardinality"]
    ec["users"] = max(2, int(ec["users"] * rng.uniform(0.5, 2.0)))
    # blue watching device/merchant fan-out -> give every user their own device,
    # multiply merchants so pairs never repeat
    if hot & {"device_users", "merchant_users", "user_merchant_repeats"}:
        ec["devices"] = max(ec["users"], int(ec["devices"] * 1.5))
        ec["merchants"] = max(int(ec["merchants"] * 2.0), ec["users"])
    else:
        ec["devices"] = max(1, int(ec["devices"] * rng.uniform(0.5, 2.0)))
        ec["merchants"] = max(1, int(ec["merchants"] * rng.uniform(0.5, 2.0)))
    # blue watching hour concentration -> stretch the window across the day
    base["window_h"] = max(1, int(base["window_h"] * _bias(
        {"hour_sin", "hour_cos", "is_night"}, 0.5, 2.0)))
    base["amount_jitter_pct"] = round(min(0.4, base["amount_jitter_pct"] * rng.uniform(0.5, 3.0)), 3)
    base["_squad_idx"] = idx
    return base


def _mutation_context(memory: StrategyMemory | None) -> str:
    if memory is None:
        return ""
    stats = memory.vector_stats()
    ctx = ""
    if stats:
        lines = [f"- {s['vector']}: attempts={s['attempts']} avg_detection={s['avg_detection']}"
                 for s in stats[:8]]
        ctx = ("\nMUTATION CONTEXT (previous rounds):\n" + "\n".join(lines)
               + "\nAvoid patterns with high avg_detection; evolve variant parameters.")
    caught = memory.caught_plans(5)
    if caught:
        c = caught[0]
        ctx += f"\nLast caught plan ({c['vector']}, detection={c['detection_rate']}): {c['evasion_notes']}"
    return ctx


async def _llm_squad_async(
    client: LLMClient, vector_id: str, profile_key: str,
    squad_size: int, gen: int, shap_ctx: str, memory: StrategyMemory | None = None,
) -> list[dict[str, Any] | None]:
    """squad_size candidate plans for one vector, generated concurrently with a
    temperature ladder + explicit diversification orders. Failed candidates
    return None (the template squad fills the gap — never lose the round)."""
    v = VECTORS[vector_id]
    p = get_profile(profile_key)
    ch = p.channels[_channel_for(v, profile_key)]
    mut = _mutation_context(memory)
    evade = ""
    if gen > 1 and shap_ctx:
        evade = ("\nDETECTOR INTELLIGENCE — the blue ensemble's top SHAP features "
                 f"right now: {shap_ctx}\nCraft parameters that are WEAK on those "
                 "features (e.g. low velocity, small amounts, few shared devices, "
                 "daylight hours — whatever starves the top features).")
    sem = asyncio.Semaphore(_SQUAD_CONCURRENCY)

    async def one(i: int) -> dict[str, Any] | None:
        async with sem:
            temp = 0.7 + 0.05 * i
            user = (
                f"Attack vector: {v['id']} {v['name']} — {v['mechanism']}\n"
                f"GenAI component: {v['genai_component']}\n"
                f"Rail profile: {p.key} (channels: {p.channel_names()})\n"
                f"Use channel '{ch.name}' (categories: {list(ch.categories)}, "
                f"amount bounds {ch.min_amount}-{ch.max_amount}).\n"
                f"{mut}{evade}\n"
                f"You are candidate #{i + 1} of {squad_size} in generation {gen} of a "
                "red-team tournament. Squadmates are exploring other parameter "
                "regions: pick a DISTINCT combination of amounts, timing, entity "
                "counts and window length — maximize the chance at least ONE squad "
                "member evades detection.\n\n"
                'Emit ONLY JSON: {"vector": str, "channel": str, '
                '"merchant_categories": [str], "structuring": [{"amount": number, "count": int}], '
                '"inter_arrival_s": {"distribution": "exponential"|"uniform"|"poisson", "min": number, "max": number}, '
                '"entity_cardinality": {"users": int, "devices": int, "merchants": int}, '
                '"amount_jitter_pct": number, "window_h": number, "rationale": str}'
            )
            try:
                raw = await client.complete("strategy", system=ARENA_SYSTEM, user=user,
                                            json_mode=True, temperature=temp)
                plan = json.loads(raw, strict=False)
                plan["vector"] = v["name"]
                plan.setdefault("channel", ch.name)
                plan["_llm_generated"] = True
                plan["_squad_idx"] = i
                return plan
            except (LLMError, json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"[arena] squad candidate {i + 1}/{squad_size} failed for "
                      f"{vector_id}: {type(e).__name__} — template fills")
                return None

    return list(await asyncio.gather(*(one(i) for i in range(squad_size))))


def run_tournament(
    *,
    profile_key: str = "card_intl",
    vector_ids: list[str] | None = None,
    n_benign: int = 2400,
    seed: int = 710,
    use_llm: bool = False,
    squad_size: int = 10,
    generations: int = 2,
    memory: StrategyMemory | None = None,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Population-based co-evolution: red fields a SQUAD per vector per
    generation; blue retrains on everything seen so far; held-out candidates
    are scored individually and the most evasive becomes the champion.
    Returns the full escalation curve across generations."""
    p = get_profile(profile_key)
    vector_ids = vector_ids or list(VECTORS.keys())[:4]
    for vid in vector_ids:
        if vid not in VECTORS:
            raise KeyError(f"unknown vector id: {vid}")
    squad_size = max(2, min(int(squad_size), 32))
    generations = max(1, min(int(generations), 5))

    amounts, hour_weights = real_anchor()
    benign_train = generate_benign(int(n_benign * 0.5), profile=p, seed=seed,
                                   amount_pool=amounts, hour_weights=hour_weights)
    benign_calib = generate_benign(int(n_benign * 0.25), profile=p, seed=seed + 555,
                                   amount_pool=amounts, hour_weights=hour_weights)
    benign_test = generate_benign(n_benign - int(n_benign * 0.5) - int(n_benign * 0.25),
                                  profile=p, seed=seed + 999,
                                  amount_pool=amounts, hour_weights=hour_weights)
    memory = memory or StrategyMemory()

    gens_out: list[dict[str, Any]] = []
    prior_campaigns: list[dict[str, Any]] = []   # everything blue has been taught
    shap_ctx = ""
    ensemble: BlueEnsemble | None = None

    for gen in range(1, generations + 1):
        # ---------------- RED: field the squad ----------------
        squads: dict[str, list[dict[str, Any]]] = {}
        n_llm = 0
        for vi, vid in enumerate(vector_ids):
            plans: list[dict[str, Any] | None] = [None] * squad_size
            if use_llm and llm is not None:
                try:
                    plans = asyncio.run(_llm_squad_async(
                        llm, vid, profile_key, squad_size, gen, shap_ctx, memory))
                except LLMError as e:
                    print(f"[arena] LLM squad failed for {vid} ({e}) — template squad")
            cands: list[dict[str, Any]] = []
            for j in range(squad_size):
                plan = plans[j]
                if plan is None:
                    plan = _squad_plan_template(vid, profile_key, j, seed + gen, shap_ctx)
                else:
                    n_llm += 1
                out = weave_attack_plan(plan, profile=p, seed=seed + 1000 * gen + 100 * vi + j)
                if not out["ok"]:
                    out = weave_attack_plan(_squad_plan_template(vid, profile_key, j, seed + gen, shap_ctx),
                                            profile=p, seed=seed + 1000 * gen + 100 * vi + j)
                if not out["ok"]:
                    # last resort: the canonical template is always weavable
                    plan = template_plan(vid, profile_key)
                    plan["_squad_idx"] = j
                    out = weave_attack_plan(plan, profile=p, seed=seed + 1000 * gen + 100 * vi + j)
                cands.append({"vector_id": vid, "plan": plan,
                              "used_llm": bool(plan.get("_llm_generated")),
                              "squad_idx": j, **out})
                cands[-1].setdefault("campaign_id", f"cmp_{p.key}_g{gen}_v{vi}_s{j}")
            squads[vid] = cands

        # ---------------- split: 70% train / 30% held-out ----------------
        train_c: list[dict[str, Any]] = []
        hold_c: list[dict[str, Any]] = []
        for vid, cands in squads.items():
            k = max(1, int(len(cands) * 0.7))
            train_c += cands[:k]
            hold_c += cands[k:]

        # ---------------- BLUE: retrain on everything seen so far ----------------
        train_atk = [t for c in prior_campaigns + train_c for t in c["txns"]]
        eval_atk = [t for c in hold_c for t in c["txns"]]
        stream = benign_train + train_atk + benign_calib + benign_test + eval_atk
        X_all = build_features(stream)
        n_bt, n_ta, n_bc = len(benign_train), len(train_atk), len(benign_calib)
        n_bb, n_ea = len(benign_test), len(eval_atk)
        X_train = X_all.iloc[: n_bt + n_ta].to_numpy()
        y_train = np.array([0] * n_bt + [1] * n_ta)
        X_calib = X_all.iloc[n_bt + n_ta: n_bt + n_ta + n_bc].to_numpy()
        X_test = X_all.iloc[n_bt + n_ta + n_bc:].to_numpy()
        y_test = np.array([0] * n_bb + [1] * n_ea)

        ensemble = BlueEnsemble(FEATURE_NAMES).fit(X_train, y_train)
        ensemble.calibrate(X_calib, target_fp=0.02)
        overall = ensemble.confusion(X_test, y_test)
        fp_rate = ensemble.confusion(X_test[:n_bb], np.zeros(n_bb))["fp_rate_on_benign"]

        # ---------------- score each held-out candidate; pick champions ----------------
        pos, champions, cand_rows = n_bb, [], []
        for vid, cands in squads.items():
            hc = cands[int(len(cands) * 0.7):]
            for c in hc:
                k = len(c["txns"])
                sl = X_test[pos: pos + k]
                det = float(np.mean(ensemble.predict(sl)["flagged"])) if k else 0.0
                c["detection_rate"], c["in_sample"], c["gen"] = det, False, gen
                cand_rows.append((vid, c, det))
                pos += k
        for vid in squads:
            vid_rows = [(v2, c, d) for (v2, c, d) in cand_rows if v2 == vid]
            if vid_rows:
                v2, c, d = min(vid_rows, key=lambda r: r[2])   # most evasive wins
                champions.append({"vector": c["plan"]["vector"], "vector_id": v2,
                                  "squad_idx": c["squad_idx"], "llm_generated": c["used_llm"],
                                  "detection_rate": round(d, 4)})
        held_det = float(np.mean([d for _, _, d in cand_rows])) if cand_rows else 0.0

        # ---------------- SHAP why on the flagged held-out rows ----------------
        flagged_idx = [i for i in range(n_ea) if bool(ensemble.predict(X_test[n_bb:][[i]])["flagged"][0])]
        why = shap_why(ensemble, X_test[n_bb:], flagged_idx[:50]) if flagged_idx \
            else "EVaded: no held-out rows flagged"
        shap_ctx = why

        # ---------------- ledger ----------------
        for vid, c, det in cand_rows:
            memory.record_campaign(
                campaign_id=f"{p.key}_g{gen}_s{c['squad_idx']}_{c['campaign_id']}",
                vector=c["plan"]["vector"], rail_profile=p.key,
                plan={k2: v2 for k2, v2 in c["plan"].items() if not str(k2).startswith("_")},
                n_txns=len(c["txns"]), n_dropped=c["dropped"], detection_rate=det,
                evasion_notes=f"gen{gen} held-out squad#{c['squad_idx']}"
                              f"{' LLM' if c['used_llm'] else ''} | why: {why[:160]}",
            )
        memory.record_round(
            campaign_id=f"{p.key}_g{gen}_tournament", blue_version=BLUE_VERSION,
            tp=overall["tp"], fp=overall["fp"], fn=overall["fn"], tn=overall["tn"],
            f1=overall["f1"],
            notes=f"TOURNAMENT gen{gen}: squad={squad_size}x{len(vector_ids)} "
                  f"llm_plans={n_llm} held_det={held_det:.3f} champions="
                  + "; ".join(f"{ch['vector']}={ch['detection_rate']}" for ch in champions),
        )

        gens_out.append({
            "gen": gen, "n_candidates": squad_size * len(vector_ids),
            "n_llm_plans": n_llm, "n_heldout": len(cand_rows),
            "held_out_detection_rate": round(held_det, 4),
            "benign_fp_rate": fp_rate, "overall": overall,
            "champions": champions, "shap_why": why,
            "candidates": [
                {"vector": c["plan"]["vector"], "squad_idx": c["squad_idx"],
                 "llm": c["used_llm"], "detection_rate": round(det, 4)}
                for (vid, c, det) in cand_rows
            ],
        })
        # blue has now seen this generation — next gen red mutates against it
        prior_campaigns += train_c + hold_c

    return {
        "mode": "tournament",
        "rail_profile": p.key,
        "blue_version": BLUE_VERSION,
        "squad_size": squad_size,
        "generations": gens_out,
        "escalation": [g["held_out_detection_rate"] for g in gens_out],
        "red_advantage": round(1.0 - min(g["held_out_detection_rate"] for g in gens_out), 4),
        "n_benign": n_benign,
        "_ensemble": ensemble,  # popped by the API layer; never serialized
    }


