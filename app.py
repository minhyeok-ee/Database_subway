from flask import Flask, render_template, request
import sqlite3
from collections import deque, defaultdict

app = Flask(__name__)
DB_PATH = "app.db"


# -----------------------------
# DB 초기화 (테이블 없으면 생성)
# -----------------------------
def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    cur = db.cursor()

    cur.execute("""
        create table if not exists Station(
            Station_id integer primary key,
            Station_name text unique not null
        );
    """)

    cur.execute("""
        create table if not exists Line(
            Line_id integer primary key,
            name text not null
        );
    """)

    cur.execute("""
        create table if not exists Route(
            Station_id integer not null references Station(Station_id),
            Line_id integer not null references Line(Line_id),
            Sequence integer not null,
            primary key (Line_id, Station_id),
            unique(Line_id, Sequence)
        );
    """)

    # "나만의 저장 경로"
    cur.execute("""
        create table if not exists SavedRoute(
            id integer primary key,
            route_name text,
            start_station_id integer not null references Station(Station_id),
            end_station_id   integer not null references Station(Station_id),
            path text not null
        );
    """)

    db.commit()
    db.close()


# -----------------------------
# 유틸: 역 이름 -> Station_id
# -----------------------------
def get_station_id(station_name):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cur.execute("select Station_id from Station where Station_name = ?;", (station_name,))
    row = cur.fetchone()
    db.close()

    if not row:
        return None
    return row["Station_id"]


# -----------------------------
# 유틸: Station_id -> 이름 dict
# -----------------------------
def get_id2name_map():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cur.execute("select Station_id, Station_name from Station;")
    rows = cur.fetchall()
    db.close()

    return {r["Station_id"]: r["Station_name"] for r in rows}


# -----------------------------
# Route 테이블로 그래프(역-역 연결) 만들기
# -----------------------------
def build_graph():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cur.execute("""
        select Line_id, Station_id, Sequence
        from Route
        order by Line_id, Sequence
    """)
    rows = cur.fetchall()
    db.close()

    adj = {}          # {station_id: set(neighbor_station_id)}
    last_by_line = {} # {line_id: prev_station_id}

    for r in rows:
        lid = r["Line_id"]
        sid = r["Station_id"]

        if sid not in adj:
            adj[sid] = set()

        if lid in last_by_line:
            prev = last_by_line[lid]
            # 양방향 연결
            adj[prev].add(sid)
            adj[sid].add(prev)

        last_by_line[lid] = sid

    return adj


# -----------------------------
# 두 역을 직접 연결하는 "가능한 노선명" 리스트
# (A역과 B역이 같은 Line에 속하면 그 Line.name 반환)
# -----------------------------
def get_lines_between(station_a_id, station_b_id):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cur.execute("""
        select L.name
        from Route R1
        join Route R2 on R1.Line_id = R2.Line_id
        join Line  L  on L.Line_id  = R1.Line_id
        where R1.Station_id = ?
          and R2.Station_id = ?
    """, (station_a_id, station_b_id))

    lines = [r["name"] for r in cur.fetchall()]
    db.close()
    return lines


# -----------------------------
# BFS로 "정차역 수(간선 수)" 최단 경로들 중 최대 k개
# -----------------------------
def find_k_shortest_paths(start_id, end_id, k=5):
    adj = build_graph()
    if start_id not in adj or end_id not in adj:
        return []

    dist = {start_id: 0}
    parents = defaultdict(list)
    q = deque([start_id])

    while q:
        v = q.popleft()
        for nb in adj[v]:
            if nb not in dist:
                dist[nb] = dist[v] + 1
                parents[nb].append(v)
                q.append(nb)
            elif dist[nb] == dist[v] + 1:
                parents[nb].append(v)

    if end_id not in dist:
        return []

    paths = []

    def backtrack(node, path):
        if len(paths) >= k:
            return
        if node == start_id:
            full = list(reversed(path + [node]))
            paths.append(full)
            return
        for p in parents[node]:
            backtrack(p, path + [node])

    backtrack(end_id, [])
    return paths


# -----------------------------
# 경로(Station_id 리스트)에 대해
# "환승역 + 노선 변경 정보"를 만들기
# - 환승역이면 현재 역에 transfer="A -> B" 붙임
# -----------------------------
def annotate_transfers(path_ids, id2name):
    detailed = []
    prev_line = None  # 직전 구간에서 선택된 노선명

    for i, sid in enumerate(path_ids):
        station_name = id2name[sid]
        transfer_text = None

        if i == 0:
            # 첫 역
            detailed.append({"name": station_name, "transfer": None})
            continue

        prev_sid = path_ids[i - 1]
        candidate_lines = get_lines_between(prev_sid, sid)

        # 후보 노선 중에서 "이전 노선"을 유지할 수 있으면 유지 (환승 최소처럼 보이게)
        chosen_line = None
        if prev_line is not None and prev_line in candidate_lines:
            chosen_line = prev_line
        else:
            chosen_line = candidate_lines[0] if candidate_lines else None

        # 노선이 바뀌면 환승
        if prev_line is not None and chosen_line is not None and chosen_line != prev_line:
            transfer_text = f"{prev_line} -> {chosen_line}"

        # 업데이트
        prev_line = chosen_line

        detailed.append({"name": station_name, "transfer": transfer_text})

    return detailed


# =======================
# 라우트
# =======================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/saved/")
def saved():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    cur.execute("""
        select SR.id,
               SR.route_name,
               s1.Station_name as start_name,
               s2.Station_name as end_name,
               SR.path
        from SavedRoute SR
        join Station s1 on SR.start_station_id = s1.Station_id
        join Station s2 on SR.end_station_id   = s2.Station_id
        order by SR.id desc;
    """)
    items = cur.fetchall()
    db.close()

    return render_template("saved.html", items=items)


@app.route("/delete/<int:route_id>/")
def delete_route(route_id):
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    cur.execute("delete from SavedRoute where id = ?;", (route_id,))
    db.commit()
    db.close()

    # redirect 없이 바로 목록 렌더
    return saved()


@app.route("/search/", methods=["GET", "POST"])
def search():
    if request.method == "GET":
        return render_template("search.html")

    start_name = request.form.get("start_name", "").strip()
    end_name = request.form.get("end_name", "").strip()

    if start_name == "" or end_name == "":
        return render_template("search.html", error="출발역/도착역을 모두 입력해줘.")

    start_id = get_station_id(start_name)
    if start_id is None:
        return render_template("search.html", error=f"출발역 '{start_name}' 을(를) 찾을 수 없어.")

    end_id = get_station_id(end_name)
    if end_id is None:
        return render_template("search.html", error=f"도착역 '{end_name}' 을(를) 찾을 수 없어.")

    id2name = get_id2name_map()
    paths_id = find_k_shortest_paths(start_id, end_id, k=5)

    if not paths_id:
        return render_template("search.html", error="해당 역 사이 경로를 찾을 수 없어. (Route 연결 확인 필요)")

    routes = []
    for p in paths_id:
        stations_detailed = annotate_transfers(p, id2name)
        routes.append({
            "length": len(p),
            "stations": stations_detailed,                 # [{name, transfer}, ...]
            "path_str": ",".join([id2name[sid] for sid in p])
        })

    return render_template("search_result.html",
                           start_name=start_name,
                           end_name=end_name,
                           routes=routes)


@app.route("/save_route/", methods=["POST"])
def save_route():
    route_name = request.form.get("route_name", "").strip()
    start_name = request.form.get("start_name", "").strip()
    end_name = request.form.get("end_name", "").strip()
    path_str = request.form.get("path_str", "").strip()

    if path_str == "" or start_name == "" or end_name == "":
        return saved()

    start_id = get_station_id(start_name)
    end_id = get_station_id(end_name)
    if start_id is None or end_id is None:
        return saved()

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    cur = db.cursor()

    cur.execute("""
        insert into SavedRoute (route_name, start_station_id, end_station_id, path)
        values (?, ?, ?, ?);
    """, (route_name, start_id, end_id, path_str))

    db.commit()
    db.close()

    return saved()


# 시작 시 테이블 준비
init_db()

if __name__ == "__main__":
    app.debug = True
    app.run(host="127.0.0.1", port=5000)
