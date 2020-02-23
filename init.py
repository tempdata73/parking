#!/usr/bin/env python
import os
import sys
import cv2
import logging
import psycopg2
import argparse

from shapely.geometry import Polygon
from utils.config import config
from utils import events


ROOT_DIR = "src"
TABLES_SQL_FILE = os.path.join(ROOT_DIR, "tables.sql")
CONFIG_INI_FILE = os.path.join(ROOT_DIR, "config.ini")


def main(video_file, num, loc):
    # connect to database
    logging.info("Connecting to database")
    db_params = config(filename=CONFIG_INI_FILE)
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    # Create necessary tables
    cur.execute("SAVEPOINT table_creation")
    try:
        logging.info("Instantiating relations")
        cur.execute(open(TABLES_SQL_FILE).read())
    except psycopg2.errors.DuplicateObject:
        logging.info("Relations are already instantiated")
        cur.execute("ROLLBACK TO SAVEPOINT table_creation")
    else:
        cur.execute("RELEASE SAVEPOINT table_creation")

    # Fetch video metadata
    cap = cv2.VideoCapture(video_file)
    res_x = int(cap.get(3))
    res_y = int(cap.get(4))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # Populate entries for cameras table
    # If the chosen camera exists, then
    # jump to populating spots
    query = """INSERT INTO cameras VALUES
                 (%s, %s, %s, %s, %s);"""

    cur.execute("SELECT id from cameras;")
    ids = [r[0] for r in cur.fetchall()]
    if num not in ids:
        cur.execute(query, (num, loc, res_x, res_y, fps))
    else:
        logging.warning("Modifying existing camera")

    # Initialize parking lots that will be later analyzed
    query = """INSERT INTO spots VALUES
               (DEFAULT, %s, ST_SetSRID(%s::geometry, %s), false, '00:00:00', false)"""
    logging.info("Select areas of interest")
    ret, frame = cap.read()
    coords = events.select_area(frame)

    # Populate entries for spots table
    for pts in coords:
        polygon = events.sort2cyclic(pts)
        spot = Polygon(polygon)
        cur.execute(query, (num, spot.wkb_hex, 4326))

    # Commit changes and close connection
    logging.info("Committing changes and closing connection to database")
    conn.commit()
    cur.close()
    conn.close()


def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("video_file", type=str,
                        help="path/to/video.mp4")
    parser.add_argument("num", type=int,
                        help="camera id that will be reading the video file")
    parser.add_argument("loc", type=str,
                        help="description of camera's location")
    return vars(parser.parse_args())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(**parse_arguments(sys.argv[1:]))
