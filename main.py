#!/usr/bin/env python
import os
import sys
import cv2
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


def main(video_file, cam_ids):
    global conn, cur

    # connect to PostgreSQL database
    db_params = config(filename=CONFIG_INI_FILE, section="postgresql")
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    # load detection model
    model = detection.load_inference_resnet50()

    # fetch areas that will be analyzed
    spots = fetch_parking_spots(cam_ids)

    # get video data
    vcap = cv2.VideoCapture(video_file)
    fps = int(vcap.get(cv2.CAP_PROP_FPS))
    frame_counter = 0

    # start analyzing parking_spot
    while vcap.isOpened():
        ret, frame = vcap.read()
        key = cv2.waitKey(fps) & 0xFF

        # end of video or user exit
        if not ret or key == ord("q"):
            print("Video stopped")
            break

        # check if parking spots are occupied every nth frame
        if frame_counter % 75 == 0:
            # set occupancy for each spot to false
            reset_occupancy()

            # detect which spots are occupied
            bboxes = detection.detect_objects(
                model, frame, [3, 4], threshold=0.5)
            occupied_spots = fetch_occupied_spots(spots, bboxes)

            # update occupancy in table for each spot
            update_occupancy(occupied_spots)

        # display results
        spots, colors = fetch_spot_colors(cam_ids)
        for spot, color in zip(spots, colors):
            coords = np.array(spot.exterior.coords, dtype="int")
            cv2.fillPoly(frame, [coords], color)
        cv2.imshow("parking lot", frame)

        # update counter
        frame_counter += 1

    # close everything
    vcap.release()
    cur.close()
    conn.close()


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


def fetch_spot_colors(cam_ids):
    color_mapper = {True: (0, 0, 255), False: (0, 255, 0)}

    query = """SELECT location, is_occupied FROM spots
               WHERE camera_id = ANY(%s)"""
    cur.execute(query, (cam_ids,))
    hex_spots, is_occupied = zip(*cur.fetchall())

    spots = [wkb.loads(hex_spot, hex=True) for hex_spot in hex_spots]
    colors = list(map(color_mapper.get, is_occupied))

    return spots, colors


def reset_occupancy():
    query = """UPDATE spots
               SET is_occupied = false;"""
    cur.execute(query)
    conn.commit()


def update_occupancy(occupied_spots):
    query = """UPDATE spots
               SET is_occupied = true
               WHERE location = ST_GeomFromWKB(%s::geometry, 4326);"""
    cur.executemany(query, occupied_spots)
    conn.commit()


def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    # TODO: Data is supposed to be fetched from
    # live feed, not from a video file.
    parser.add_argument("video_file", type=str,
                        help="path/to/video.mp4")
    parser.add_argument("cam_ids", type=int, nargs="+",
                        help="section to which analyze")
    return vars(parser.parse_args())


if __name__ == "__main__":
    main(**parse_arguments(sys.argv[1:]))
