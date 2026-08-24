"""
Rail Profiles — LiveFire's global rail/region abstraction.

One arena, N region profiles. Each profile parameterizes the constraint
engine with rail-true limits, categories, currency, geography, and defense
mechanics (SCA step-up, chargebacks) so attack survival can be compared
per rail — the Robustness Ledger's multi-rail story.

Authority rules (see docs/AUDIT.md rule 3):
  - The `upi_in` profile wraps the vendored ARGUS dataset_config verbatim;
    that file remains the single source of truth for Indian rails.
  - Card profiles are calibrated to public card-network mechanics:
    CNP vs CP channels, issuer-set ceilings, 3DS/SCA step-up (PSD2 RTS for EU),
    Reg E/Z dispute rights (US), chargeback flows.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_VENDOR_ML = Path(__file__).resolve().parents[1] / "vendor" / "argus" / "backend" / "ml"
if str(_VENDOR_ML) not in sys.path:
    sys.path.insert(0, str(_VENDOR_ML))


@dataclass(frozen=True)
class ChannelSpec:
    """One payment channel inside a rail profile."""
    name: str
    weight: float                 # share of benign traffic on this channel
    min_amount: float
    max_amount: float
    categories: tuple[str, ...]
    single_cap: float | None = None   # regulatory/issuer single-txn cap


@dataclass(frozen=True)
class RailProfile:
    key: str
    display_name: str
    currency: str
    timezone_name: str
    cities: tuple[dict[str, Any], ...]      # geo anchors: name, lat, lon, weight
    channels: dict[str, ChannelSpec]
    sca_step_up: bool = False               # 3DS/SCA available as defense mechanic
    chargebacks: bool = True                # dispute rights exist (cards) or not (UPI push)
    notes: str = ""

    def channel_names(self) -> list[str]:
        return list(self.channels.keys())


# --------------------------------------------------------------------------
# upi_in — India / UPI-first profile. Delegates to vendored ARGUS config
# (NPCI/RBI calibrated). Kept verbatim so the audit authority is preserved.
# --------------------------------------------------------------------------
def _build_upi_in() -> RailProfile:
    from dataset_config import CHANNELS, INDIAN_CITIES  # noqa: E402  (vendored authority)

    cap_by_channel = {"upi": 100_000.0, "atm": 25_000.0, "wallet": 10_000.0}
    channels = {
        name: ChannelSpec(
            name=name,
            weight=float(cfg.get("weight", 0.1)),
            min_amount=float(cfg["min"]),
            max_amount=float(cfg["max"]),
            categories=tuple(cfg["categories"]),
            single_cap=cap_by_channel.get(name),
        )
        for name, cfg in CHANNELS.items()
    }
    return RailProfile(
        key="upi_in",
        display_name="India — UPI/ATM/Wallet (NPCI/RBI calibrated)",
        currency="INR",
        timezone_name="Asia/Kolkata",
        cities=tuple(INDIAN_CITIES),
        channels=channels,
        sca_step_up=False,          # UPI push: no 3DS-style step-up; PIN per txn
        chargebacks=False,          # irreversible push payments — raises SE/social-eng fraud
        notes="Vendored ARGUS dataset_config is the authority (docs/AUDIT.md rule 3).",
    )


# --------------------------------------------------------------------------
# Card rails — shared category vocabulary, profile-specific limits/geo.
# --------------------------------------------------------------------------
_CARD_CATEGORIES = (
    "Grocery", "Restaurant", "Fuel Station", "E-commerce", "Retail Store",
    "Clothing", "Electronics", "Travel Booking", "Hotel", "Subscription",
    "Pharmacy", "Entertainment", "Digital Goods", "Gaming", "ATM Cash",
)


def _card_channels(*, cnp_max: float, cp_max: float, cash_max: float) -> dict[str, ChannelSpec]:
    return {
        "card_not_present": ChannelSpec(
            name="card_not_present", weight=0.55, min_amount=0.5, max_amount=cnp_max,
            categories=tuple(c for c in _CARD_CATEGORIES if c != "ATM Cash"),
        ),
        "card_present": ChannelSpec(
            name="card_present", weight=0.35, min_amount=0.5, max_amount=cp_max,
            categories=tuple(c for c in _CARD_CATEGORIES if c not in ("Digital Goods", "E-commerce")),
        ),
        "atm": ChannelSpec(
            name="atm", weight=0.10, min_amount=20.0, max_amount=cash_max,
            categories=("ATM Cash",),
            single_cap=cash_max,
        ),
    }


_GLOBAL_CITIES = (
    {"name": "New York", "lat": 40.71, "lon": -74.01, "weight": 0.14},
    {"name": "London", "lat": 51.51, "lon": -0.13, "weight": 0.12},
    {"name": "Singapore", "lat": 1.35, "lon": 103.82, "weight": 0.09},
    {"name": "Dubai", "lat": 25.20, "lon": 55.27, "weight": 0.08},
    {"name": "Hong Kong", "lat": 22.32, "lon": 114.17, "weight": 0.07},
    {"name": "San Francisco", "lat": 37.77, "lon": -122.42, "weight": 0.10},
    {"name": "Chicago", "lat": 41.88, "lon": -87.63, "weight": 0.07},
    {"name": "Toronto", "lat": 43.65, "lon": -79.38, "weight": 0.06},
    {"name": "Sydney", "lat": -33.87, "lon": 151.21, "weight": 0.06},
    {"name": "Frankfurt", "lat": 50.11, "lon": 8.68, "weight": 0.06},
    {"name": "Amsterdam", "lat": 52.37, "lon": 4.90, "weight": 0.05},
    {"name": "Sao Paulo", "lat": -23.55, "lon": -46.63, "weight": 0.05},
    {"name": "Mexico City", "lat": 19.43, "lon": -99.13, "weight": 0.03},
    {"name": "Johannesburg", "lat": -26.20, "lon": 28.05, "weight": 0.02},
)

_EU_CITIES = (
    {"name": "Paris", "lat": 48.86, "lon": 2.35, "weight": 0.15},
    {"name": "Berlin", "lat": 52.52, "lon": 13.40, "weight": 0.13},
    {"name": "Madrid", "lat": 40.42, "lon": -3.70, "weight": 0.12},
    {"name": "Rome", "lat": 41.90, "lon": 12.50, "weight": 0.11},
    {"name": "Amsterdam", "lat": 52.37, "lon": 4.90, "weight": 0.10},
    {"name": "Frankfurt", "lat": 50.11, "lon": 8.68, "weight": 0.10},
    {"name": "Brussels", "lat": 50.85, "lon": 4.35, "weight": 0.08},
    {"name": "Vienna", "lat": 48.21, "lon": 16.37, "weight": 0.08},
    {"name": "Dublin", "lat": 53.35, "lon": -6.26, "weight": 0.07},
    {"name": "Lisbon", "lat": 38.72, "lon": -9.14, "weight": 0.06},
)

_US_CITIES = (
    {"name": "New York", "lat": 40.71, "lon": -74.01, "weight": 0.16},
    {"name": "Los Angeles", "lat": 34.05, "lon": -118.24, "weight": 0.13},
    {"name": "Chicago", "lat": 41.88, "lon": -87.63, "weight": 0.10},
    {"name": "Houston", "lat": 29.76, "lon": -95.37, "weight": 0.08},
    {"name": "Phoenix", "lat": 33.45, "lon": -112.07, "weight": 0.07},
    {"name": "Miami", "lat": 25.76, "lon": -80.19, "weight": 0.07},
    {"name": "Atlanta", "lat": 33.75, "lon": -84.39, "weight": 0.07},
    {"name": "Dallas", "lat": 32.78, "lon": -96.80, "weight": 0.07},
    {"name": "Seattle", "lat": 47.61, "lon": -122.33, "weight": 0.06},
    {"name": "Denver", "lat": 39.74, "lon": -104.99, "weight": 0.06},
    {"name": "Boston", "lat": 42.36, "lon": -71.06, "weight": 0.07},
    {"name": "San Francisco", "lat": 37.77, "lon": -122.42, "weight": 0.06},
)


def _build(key: str, display: str, currency: str, tz: str, cities, channels,
           sca: bool, notes: str) -> RailProfile:
    return RailProfile(
        key=key, display_name=display, currency=currency, timezone_name=tz,
        cities=tuple(cities), channels=channels, sca_step_up=sca, chargebacks=True,
        notes=notes,
    )


CARD_INTL = _build(
    "card_intl", "Global card rails (Mastercard-flavored default)", "USD",
    "America/New_York", _GLOBAL_CITIES,
    _card_channels(cnp_max=25_000.0, cp_max=50_000.0, cash_max=1_000.0),
    sca=True,
    notes="3DS step-up on CNP above issuer risk thresholds; global city anchors.",
)

EU_PSD2 = _build(
    "eu_psd2", "EU card rails under PSD2 SCA", "EUR",
    "Europe/Paris", _EU_CITIES,
    _card_channels(cnp_max=20_000.0, cp_max=40_000.0, cash_max=500.0),
    sca=True,
    notes="PSD2 RTS: SCA mandatory on CNP; exemptions (TRA/low-value) modeled as step-up probability.",
)

US_CNP = _build(
    "us_cnp", "US card rails — no SCA mandate", "USD",
    "America/Chicago", _US_CITIES,
    _card_channels(cnp_max=30_000.0, cp_max=50_000.0, cash_max=800.0),
    sca=False,
    notes="No SCA mandate: card-testing historically thrives here; Reg E/Z disputes after the fact.",
)

UPI_IN = _build_upi_in()


PROFILES: dict[str, RailProfile] = {
    CARD_INTL.key: CARD_INTL,
    EU_PSD2.key: EU_PSD2,
    US_CNP.key: US_CNP,
    UPI_IN.key: UPI_IN,
}


def get_profile(key: "str | RailProfile | None") -> RailProfile:
    """Resolve a profile by key (or pass-through an instance); None → upi_in."""
    if key is None:
        return UPI_IN
    if isinstance(key, RailProfile):
        return key
    if key not in PROFILES:
        raise KeyError(f"unknown rail profile: {key!r} (have: {sorted(PROFILES)})")
    return PROFILES[key]


if __name__ == "__main__":
    for p in PROFILES.values():
        assert abs(sum(c["weight"] for c in p.cities) - 1.0) < 0.05, p.key
        total_w = sum(c.weight for c in p.channels.values())
        assert 0.99 <= total_w <= 1.01, (p.key, total_w)
        for ch in p.channels.values():
            assert ch.min_amount <= ch.max_amount
            if ch.single_cap is not None:
                assert ch.single_cap <= ch.max_amount + 1e-9
        print(f"[OK] {p.key}: {len(p.channels)} channels, {len(p.cities)} cities, sca={p.sca_step_up}")
    print("[OK] rail profiles selftest passed")

