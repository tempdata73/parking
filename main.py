#!/usr/bin/env python
import os
import sys
import cv2
import time
import datetime
import psycopg2
import argparse
import numpy as np

from shapely import wkb
from shapely.geometry import box
from scipy.spatial import cKDTree

from utils.config import config
from utils import detection


ROOT_DIR = "src"
CONFIG_INI_FILE = os.path.join(ROOT_DIR, "config.ini")


def main(args):
    global conn, cur

    # connect to PostgreSQL database
    db_params = config(filename=CONFIG_INI_FILE)
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    # load detection model
    model = detection.load_inference_resnet50()

    # fetch areas that will be analyzed
    spots = fetch_parking_spots(args.cam_ids)

    # get video data
    vcap = cv2.VideoCapture(args.video_file)
    fps = int(vcap.get(cv2.CAP_PROP_FPS))
    frame_counter = 0
    detection_interval = fps * time2seconds(args.time_interval)

    # start analyzing parking lot
    while vcap.isOpened():
        ret, frame = vcap.read()
        key = cv2.waitKey(fps) & 0xFF

        # end of video or user exit
        if not ret or key == ord("q"):
            print("Video stopped")
            break

        # check if parking spots are occupied every nth frame
        if frame_counter % detection_interval == 0:
            # set occupancy for each spot to false
            reset_occupancy(args.cam_ids)

            # detect which spots are occupied
            bboxes = detection.detect_objects(
                model, frame, [3, 4], threshold=0.5)
            occupied_spots = fetch_occupied_spots(spots, bboxes)

            # update occupancy in table for each spot
            update_occupancy(occupied_spots)
            
        # check if spot_time > time_threshold
        update_occupied_time(fps)
        update_overtime(args.limit)
        frame_counter += 1

        # display video
        frame = display(frame)
        cv2.imshow("parking lot", frame)

    # reset and close connections
    vcap.release()
    reset()
    cur.close()
    conn.close()


def display(frame):
    cur.execute("SELECT location, is_occupied, is_overtime FROM spots;")
    hex_poly, is_occupied, is_overtime = zip(*cur.fetchall())
    poly = [wkb.loads(hpoly, hex=True) for hpoly in hex_poly]
        
    for spot, occupied, overtime in zip(poly, is_occupied, is_overtime):
        if overtime:
            color = (255, 0, 0)
        elif occupied:
            color = (0, 0, 255)
        else:
            color = (0, 255, 0)

        coords = np.array(spot.exterior.coords, dtype="int")
        cv2.fillPoly(frame, [coords], color)

    return frame


def time2seconds(time_interval):
    x = time.strptime(time_interval, "%H:%M:%S")
    seconds = datetime.timedelta(
        hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds()
    return int(seconds)


def fetch_parking_spots(cam_ids):
    # get hex locations of parking spots
    query = """SELECT location FROM spots
               WHERE camera_id = ANY(%s)"""
    cur.execute(query, (cam_ids,))
    hex_spots =  [r[0] for r in cur.fetchall()]

    # convert to shapely objects
    spots = [wkb.loads(hex_spot, hex=True) for hex_spot in hex_spots]
    return spots


def fetch_occupied_spots(spots, candidates):
    occupied_spots = []
    centroids = detection.fetch_centroids(candidates)
    tree = cKDTree(centroids)

    # get nearest detected car for each spot
    for spot in spots:
        dist, idx = tree.query(spot.centroid, k=1)
        candidate = box(*candidates[idx])
        # if overlap > threshold then spot is occupied
        if detection.is_occupied(spot, candidate):
            occupied_spots.append((spot.wkb_hex,))
    
    return occupied_spots


def reset_occupancy(cam_ids):
    query = """UPDATE spots
               SET is_occupied = false
               WHERE camera_id = ANY(%s);"""
    cur.execute(query, (cam_ids,))
    conn.commit()


def reset():
    query = """UPDATE spots
               SET is_occupied = false,
                   occupied_time = '00:00:00',
                   is_overtime = false"""
    cur.execute(query)
    conn.commit()


def update_occupancy(occupied_spots):
    query = """UPDATE spots
               SET is_occupied = true
               WHERE location = ST_GeomFromWKB(%s::geometry, 4326);"""
    cur.executemany(query, occupied_spots)
    conn.commit()


def update_occupied_time(fps):
    # add time to occupied spots
    query = """UPDATE spots
               SET occupied_time = occupied_time + interval '%s seconds'
               WHERE is_occupied = true;"""
    cur.execute(query, (1/fps,))

    # reset time to newly available spots
    query = """UPDATE spots
               SET occupied_time = '00:00:00',
                   is_overtime = false
               WHERE is_occupied = false;"""
    cur.execute(query)
    conn.commit()


def update_overtime(limit):
    query = """UPDATE spots
               SET is_overtime = true
               WHERE occupied_time > %s;"""
    cur.execute(query, (limit,))
    conn.commit()


def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    # TODO: Data is supposed to be fetched from
    # live feed, not from a video file.
    parser.add_argument("video_file", type=str,
                        help="path/to/video.mp4")
    parser.add_argument("cam_ids", type=int, nargs="+",
                        help="section to which analyze")
    parser.add_argument("--time_interval", "-t", type=str, default="00:00:05",
                        help="do object detection every time interval")
    parser.add_argument("--limit", "-l", type=str, default="00:00:15",
                        help="Allowed time for parked vehicle")

    return parser.parse_args()


if __name__ == "__main__":
    main(parse_arguments(sys.argv[1:]))
