import sqlite3

DB_PATH = "app.db"

Line_data = {
    "1호선":[
        "인천", "동인천", "도원", "제물포", "도화", ""
    ],
    "2호선":[
        "", ""
    ]
}


def main():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    cursor = db.cursor()
    
    for Line_name, Stations in Line_data.items():
        