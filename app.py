from flask import Flask, render_template, request
import sqlite3, json, os

app = Flask(__name__)
DB_PATH = 'app.db'

db = sqlite3.connect(DB_PATH)
db.execute("PRAGMA foreign_keys = ON")

cursor = db.cursor()

cursor.execute("""
        create table Station(
            Station_id integer primary key,
            Station_name text unique not null
        );     
""")

cursor.execute("""
        create table Line(
            Line_id integer primary key,
            name text not null
        );
""")

cursor.execute("""
        create table Route(
            Station_id integer not null references Station(Station_id),
            Line_id integer not null references Line(Line_id),
            Sequence integer not null,
            primary key (Line_id, Station_id),
            unique(Line_id, Sequence)
        );
""")