import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Rectangle,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";

const pin = L.divIcon({
  className: "map-pin",
  html: "<span></span>",
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});
const MAX_SPAN = 10;
const MIN_SPAN = 0.2;

function normalise(a, b) {
  let south = Math.min(a.lat, b.lat);
  let north = Math.max(a.lat, b.lat);
  let west = Math.min(a.lng, b.lng);
  let east = Math.max(a.lng, b.lng);
  if (north - south > MAX_SPAN) north = south + MAX_SPAN;
  if (east - west > MAX_SPAN) east = west + MAX_SPAN;
  if (north - south < MIN_SPAN) {
    const c = (north + south) / 2;
    south = c - MIN_SPAN / 2;
    north = c + MIN_SPAN / 2;
  }
  if (east - west < MIN_SPAN) {
    const c = (east + west) / 2;
    west = c - MIN_SPAN / 2;
    east = c + MIN_SPAN / 2;
  }
  const r = (x) => Math.round(x * 100) / 100;
  return {
    south: r(Math.max(-90, south)),
    west: r(Math.max(-180, west)),
    north: r(Math.min(90, north)),
    east: r(Math.min(180, east)),
  };
}

function Layer({ mode, region, onPoint, onBox }) {
  const map = useMap();
  const [drag, setDrag] = useState(null);

  useEffect(() => {
    const c = map.getContainer();
    if (mode === "box") {
      map.dragging.disable();
      c.style.cursor = "crosshair";
    } else {
      map.dragging.enable();
      c.style.cursor = "";
    }
    return () => {
      map.dragging.enable();
      c.style.cursor = "";
    };
  }, [mode, map]);

  useMapEvents({
    click(e) {
      if (mode === "pin") {
        const p = e.latlng.wrap();
        onPoint(p.lat, p.lng);
      }
    },
    mousedown(e) {
      if (mode === "box") setDrag({ a: e.latlng.wrap(), b: e.latlng.wrap() });
    },
    mousemove(e) {
      if (mode === "box" && drag)
        setDrag((d) => ({ ...d, b: e.latlng.wrap() }));
    },
    mouseup(e) {
      if (mode === "box" && drag) {
        const box = normalise(drag.a, e.latlng.wrap());
        setDrag(null);
        onBox(box);
      }
    },
  });

  const n = (v) => Number(v);
  const isBox = region.kind === "box";
  const ok = isBox
    ? [region.south, region.west, region.north, region.east].every((v) =>
        Number.isFinite(n(v)),
      )
    : Number.isFinite(n(region.lat)) && Number.isFinite(n(region.lon));

  useEffect(() => {
    if (!ok) return;
    if (isBox) {
      const b = L.latLngBounds(
        [n(region.south), n(region.west)],
        [n(region.north), n(region.east)],
      );
      if (!map.getBounds().contains(b))
        map.fitBounds(b.pad(0.5), { maxZoom: 8 });
    } else if (
      !map
        .getBounds()
        .pad(-0.1)
        .contains([n(region.lat), n(region.lon)])
    ) {
      map.flyTo([n(region.lat), n(region.lon)], Math.max(map.getZoom(), 6));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    region.lat,
    region.lon,
    region.south,
    region.west,
    region.north,
    region.east,
    ok,
  ]);

  return (
    <>
      {ok && !isBox && (
        <Marker
          position={[n(region.lat), n(region.lon)]}
          icon={pin}
          keyboard={false}
        />
      )}
      {ok && isBox && (
        <Rectangle
          bounds={[
            [n(region.south), n(region.west)],
            [n(region.north), n(region.east)],
          ]}
          pathOptions={{
            color: "#0c1a33",
            weight: 2,
            fillColor: "#ef8a62",
            fillOpacity: 0.28,
          }}
        />
      )}
      {drag && (
        <Rectangle
          bounds={[
            [drag.a.lat, drag.a.lng],
            [drag.b.lat, drag.b.lng],
          ]}
          pathOptions={{
            color: "#0c1a33",
            weight: 1.5,
            dashArray: "5 5",
            fillOpacity: 0.1,
          }}
        />
      )}
    </>
  );
}

export default function MapPicker({ region, mode, onPoint, onBox }) {
  const lat = Number.isFinite(
    Number(region.lat ?? (Number(region.south) + Number(region.north)) / 2),
  )
    ? Number(region.lat ?? (Number(region.south) + Number(region.north)) / 2)
    : 20;
  const lon = Number.isFinite(
    Number(region.lon ?? (Number(region.west) + Number(region.east)) / 2),
  )
    ? Number(region.lon ?? (Number(region.west) + Number(region.east)) / 2)
    : 0;
  return (
    <MapContainer
      center={[lat, lon]}
      zoom={5}
      minZoom={2}
      scrollWheelZoom={false}
      worldCopyJump
      className="map"
      attributionControl
    >
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={18}
      />
      <Layer mode={mode} region={region} onPoint={onPoint} onBox={onBox} />
    </MapContainer>
  );
}
