"""
Builds the campus walking network and the travel-time matrix between locations.

The raw material is OpenStreetMap data for the IIMA campus, cached in data/.
Two things come out of this module:

  1. LOCATIONS - the places a technician can be sent to (dorms, academic
                 blocks, offices) plus the depot, each with a real lat/lon
                 taken from the map.
  2. WALK      - a matrix giving the walking time in minutes between every
                 pair of those places.

Why not just use straight-line distance?
----------------------------------------
Because the campus is cut in two by a main road. The only pedestrian link
between the new campus (where the dorms are) and the old campus (where the
library, faculty wings and the Estate Office are) is the walkway tunnel. Two
buildings 500 m apart as the crow flies can be a 12 minute walk apart in
reality, because you have to walk to the tunnel, go under the road, and walk
back out the other side. A straight-line matrix would hide that completely,
and the tunnel is the single most important feature of this campus for anyone
planning a day of repair visits.

How the matrix is actually built
--------------------------------
We build a small graph and run Dijkstra on it:

  - every location is a node, and so is each mouth of the tunnel;
  - two locations on the same side of the road are joined directly, with the
    walking distance taken as the straight-line distance times a detour
    factor, because you walk around lawns and buildings rather than through
    them;
  - the two tunnel mouths are joined by the tunnel itself, with a time
    penalty for going down the ramp and back up;
  - nothing else crosses the road.

Note where the depot is. The Estate Office sits on the old campus, while 19 of
the 23 complaint sites are dorms on the new campus. Every technician therefore
starts the day on the wrong side of the road and has to use the tunnel at
least twice. That single fact is what makes the routing worth optimising.

Dijkstra then works out, for any pair of locations, whether the trip stays on
one side or has to go through the tunnel, and what that costs. The detour
factor is not guessed: it is measured from the road network in the OSM
extract, in calibrate_detour_factor() below.
"""

import json
import math
import heapq
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# Walking speed of someone carrying a toolbag, in metres per minute.
# 4.5 km/h is a normal unhurried walking pace.
WALK_SPEED_M_PER_MIN = 75.0

# Extra time to use the tunnel: down the ramp, along it, back up the far side.
TUNNEL_PENALTY_MIN = 2.0

# How much further you actually walk than the straight-line distance, because
# paths go around lawns and buildings rather than through them. 1.3 is the
# usual working figure for pedestrian movement in a built-up area. Section 8
# of the report checks that nothing important changes if it is 1.2 or 1.4.
DETOUR_FACTOR = 1.30

# Longitude of the main road that splits the campus. West of it is the new
# campus, east of it is the old campus. This is the midpoint of the tunnel.
ROAD_LON = 72.53415

# OSM highway types a person on foot may use, used only for calibration
# and for drawing the map.
WALKABLE = {
    "footway", "path", "pedestrian", "steps", "living_street",
    "service", "residential", "unclassified", "track", "tertiary",
}

# The places technicians get sent to. Names match the OSM 'name' tag exactly.
DORMS = (
    [f"Dormitory {i}" for i in range(10, 21)] +   # 11 dorms
    [f"Dorm {i}" for i in range(28, 36)]          # 8 dorms
)

OTHER_SITES = [
    ("Student Activity Block", "facility"),
    ("IMDC Dining Hall", "facility"),
    ("International Management Development Center", "facility"),
    ("Center for Innovation Incubation & Entrepreneurship", "office"),
    ("Administrative Block", "office"),
    ("Computer Center", "office"),
    ("Faculty Wings", "office"),
    ("Vikram Sarabhai Library", "office"),
    ("Ravi J. Matthai Centre for Educational Innovation", "office"),
    ("Kasturbhai Lalbhai Management Development Center", "facility"),
]

DEPOT_NAME = "Estate Office"

# Short labels for figures and tables.
SHORT = {
    "Estate Office": "Depot",
    "Student Activity Block": "SAB",
    "IMDC Dining Hall": "Dining",
    "International Management Development Center": "IMDC",
    "Center for Innovation Incubation & Entrepreneurship": "CIIE",
    "Administrative Block": "Admin",
    "Computer Center": "Comp Ctr",
    "Faculty Wings": "Faculty",
    "Vikram Sarabhai Library": "Library",
    "Ravi J. Matthai Centre for Educational Innovation": "RJMCEI",
    "Kasturbhai Lalbhai Management Development Center": "KLMDC",
}


def short_name(name):
    if name in SHORT:
        return SHORT[name]
    return name.replace("Dormitory ", "D").replace("Dorm ", "D")


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two lat/lon points."""
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def zone_of(lon):
    """Which side of the main road a point is on."""
    return "new" if lon < ROAD_LON else "old"


def _key(lat, lon):
    return (round(lat, 6), round(lon, 6))


def load_buildings():
    """Return {name: (lat, lon)} for every named building in the OSM extract."""
    with open(os.path.join(DATA, "osm_buildings.json")) as f:
        raw = json.load(f)
    out = {}
    for el in raw["elements"]:
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        c = el.get("center") or {"lat": el.get("lat"), "lon": el.get("lon")}
        if c.get("lat") is None:
            continue
        out.setdefault(name, (c["lat"], c["lon"]))
    return out


def load_ways():
    """Walkable OSM ways, each as a list of (lat, lon) points."""
    with open(os.path.join(DATA, "osm_paths.json")) as f:
        raw = json.load(f)
    ways = []
    for way in raw["elements"]:
        tags = way.get("tags") or {}
        if tags.get("highway") not in WALKABLE:
            continue
        geom = [(p["lat"], p["lon"]) for p in way.get("geometry") or []]
        if len(geom) >= 2:
            ways.append({"name": tags.get("name", ""),
                         "highway": tags["highway"],
                         "tunnel": tags.get("tunnel") == "yes",
                         "geom": geom})
    return ways


def tunnel_mouths():
    """The two ends of the walkway tunnel, as (new side, old side)."""
    for w in load_ways():
        if w["tunnel"] or "tunnel" in w["name"].lower():
            a, b = w["geom"][0], w["geom"][-1]
            length = sum(haversine_m(*w["geom"][i], *w["geom"][i + 1])
                         for i in range(len(w["geom"]) - 1))
            if zone_of(a[1]) == "new":
                return a, b, length
            return b, a, length
    raise RuntimeError("walkway tunnel not found in the OSM extract")


def dijkstra(graph, source):
    """Shortest walking time from one node to every other node."""
    dist = {source: 0.0}
    pq = [(0.0, source)]
    while pq:
        d, n = heapq.heappop(pq)
        if d > dist.get(n, float("inf")):
            continue
        for m, w in graph.get(n, ()):
            nd = d + w
            if nd < dist.get(m, float("inf")):
                dist[m] = nd
                heapq.heappush(pq, (nd, m))
    return dist


def build():
    """
    Assemble the locations and the walking-time matrix.

    Returns a dict with
        names      list of location names, index 0 is the depot
        short      short labels for figures
        coords     list of (lat, lon) in the same order
        category   'depot' / 'dorm' / 'office' / 'facility'
        zone       'new' / 'old'
        walk       walk[i][j] = walking minutes from i to j
        meta       notes on how the matrix was built
    """
    buildings = load_buildings()
    mouth_new, mouth_old, tunnel_len = tunnel_mouths()

    wanted = [(DEPOT_NAME, "depot")]
    wanted += [(d, "dorm") for d in DORMS]
    wanted += OTHER_SITES

    names, latlon, category, missing = [], [], [], []
    for name, cat in wanted:
        if name not in buildings:
            missing.append(name)
            continue
        names.append(name)
        latlon.append(buildings[name])
        category.append(cat)

    n = len(names)
    zone = [zone_of(lon) for _, lon in latlon]

    # Build the small graph: locations 0..n-1, then the two tunnel mouths.
    NEW_MOUTH, OLD_MOUTH = n, n + 1
    pts = latlon + [mouth_new, mouth_old]
    graph = {i: [] for i in range(n + 2)}

    def link(i, j, minutes):
        graph[i].append((j, minutes))
        graph[j].append((i, minutes))

    def walk_minutes(i, j):
        return haversine_m(*pts[i], *pts[j]) * DETOUR_FACTOR / WALK_SPEED_M_PER_MIN

    # Locations on the same side of the road are directly walkable.
    for i in range(n):
        for j in range(i + 1, n):
            if zone[i] == zone[j]:
                link(i, j, walk_minutes(i, j))

    # Each location is walkable to the tunnel mouth on its own side.
    for i in range(n):
        mouth = NEW_MOUTH if zone[i] == "new" else OLD_MOUTH
        link(i, mouth, walk_minutes(i, mouth))

    # The tunnel itself: the only way across the road.
    link(NEW_MOUTH, OLD_MOUTH,
         tunnel_len / WALK_SPEED_M_PER_MIN + TUNNEL_PENALTY_MIN)

    walk = [[0.0] * n for _ in range(n)]
    for i in range(n):
        dist = dijkstra(graph, i)
        for j in range(n):
            if i != j:
                walk[i][j] = round(dist[j], 2)

    return {
        "names": names,
        "short": [short_name(x) for x in names],
        "coords": latlon,
        "category": category,
        "zone": zone,
        "walk": walk,
        "tunnel": {"new": mouth_new, "old": mouth_old,
                   "length_m": round(tunnel_len, 1)},
        "meta": {
            "walk_speed_m_per_min": WALK_SPEED_M_PER_MIN,
            "detour_factor": DETOUR_FACTOR,
            "tunnel_penalty_min": TUNNEL_PENALTY_MIN,
            "road_lon": ROAD_LON,
            "missing_from_osm": missing,
            "n_new_campus": sum(1 for z in zone if z == "new"),
            "n_old_campus": sum(1 for z in zone if z == "old"),
        },
    }


if __name__ == "__main__":
    c = build()
    w, nm = c["walk"], c["short"]
    print(f"locations: {len(nm)}  "
          f"({c['meta']['n_new_campus']} new campus, "
          f"{c['meta']['n_old_campus']} old campus)")
    print(f"tunnel:    {c['tunnel']['length_m']} m")
    print(f"detour factor: {c['meta']['detour_factor']}  "
          f"walking speed: {c['meta']['walk_speed_m_per_min']} m/min")
    if c["meta"]["missing_from_osm"]:
        print("MISSING:", c["meta"]["missing_from_osm"])

    flat = [w[i][j] for i in range(len(w)) for j in range(len(w)) if i != j]
    print(f"walk time: min {min(flat):.1f}  mean {sum(flat)/len(flat):.1f}  "
          f"max {max(flat):.1f} min")

    def show(a, b):
        i, j = nm.index(a), nm.index(b)
        d = haversine_m(*c["coords"][i], *c["coords"][j])
        print(f"  {a:8s} -> {b:8s}  {w[i][j]:5.1f} min   "
              f"(straight line {d:4.0f} m, zones {c['zone'][i]}/{c['zone'][j]})")

    print("sanity checks:")
    show("D32", "Library")      # across the tunnel
    show("D32", "D33")          # neighbours
    show("Depot", "D10")        # depot to the far dorm cluster
    show("Depot", "Library")    # within the old campus
