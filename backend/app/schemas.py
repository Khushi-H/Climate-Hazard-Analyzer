"""Validated request objects shared by routes and services."""
import hashlib
import json
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .config import ALGO_VERSION, settings


@dataclass(frozen=True)
class Region:
    kind: str  # "point" | "box"
    lat: Optional[float] = None
    lon: Optional[float] = None
    south: Optional[float] = None
    west: Optional[float] = None
    north: Optional[float] = None
    east: Optional[float] = None

    def sample_points(self) -> List[Tuple[float, float]]:
        """A point is one grid cell; a box is sampled on a 2x2 grid at quarter positions and averaged."""
        if self.kind == "point":
            return [(round(self.lat, 2), round(self.lon, 2))]
        lats = [self.south + (self.north - self.south) * f for f in (0.25, 0.75)]
        lons = [self.west + (self.east - self.west) * f for f in (0.25, 0.75)]
        return [(round(a, 2), round(b, 2)) for a in lats for b in lons]

    def centroid(self) -> Tuple[float, float]:
        if self.kind == "point":
            return self.lat, self.lon
        return (self.south + self.north) / 2, (self.west + self.east) / 2

    def to_dict(self) -> dict:
        c = self.centroid()
        d = {"kind": self.kind, "centroid": {"lat": round(c[0], 3), "lon": round(c[1], 3)},
             "points": [list(p) for p in self.sample_points()]}
        if self.kind == "point":
            d.update(lat=self.lat, lon=self.lon)
        else:
            d.update(south=self.south, west=self.west, north=self.north, east=self.east)
        return d


def build_region(lat, lon, south, west, north, east) -> Region:
    box = [south, west, north, east]
    if all(v is not None for v in box):
        if north <= south or east <= west:
            raise ValueError("Box must have north > south and east > west (boxes crossing the antimeridian are not supported).")
        if (north - south) > settings.max_box_span_deg or (east - west) > settings.max_box_span_deg:
            raise ValueError(f"Box is too large. Keep each side under {settings.max_box_span_deg:g} degrees.")
        if (north - south) < settings.min_box_span_deg or (east - west) < settings.min_box_span_deg:
            raise ValueError(f"Box is too small. Make each side at least {settings.min_box_span_deg:g} degrees.")
        return Region("box", south=round(south, 2), west=round(west, 2), north=round(north, 2), east=round(east, 2))
    if lat is not None and lon is not None and not any(v is not None for v in box):
        return Region("point", lat=round(lat, 2), lon=round(lon, 2))
    raise ValueError("Provide either lat and lon, or all of south, west, north and east.")


@dataclass(frozen=True)
class AnalysisParams:
    region: Region
    start_year: int
    end_year: int
    percentile: float
    min_days: int
    method: str
    hazard: str
    name: str

    def key(self) -> str:
        raw = json.dumps(
            {
                "r": self.region.to_dict()["points"],
                "k": self.region.kind,
                "s": self.start_year,
                "e": self.end_year,
                "p": round(self.percentile, 2),
                "m": self.min_days,
                "t": self.method,
                "h": self.hazard,
                "v": ALGO_VERSION,
            },
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def to_dict(self) -> dict:
        return {
            "hazard": self.hazard,
            "start_year": self.start_year,
            "end_year": self.end_year,
            "percentile": self.percentile,
            "min_days": self.min_days,
            "method": self.method,
        }
