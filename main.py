#!/usr/bin/env python
import os
import sys
import cv2
import psycopg2
import argparse

from shapely import wkb

from utils.config import config
from utils import detection


ROOT_DIR = "src"
CONFIG_INI_FILE = os.path.join(ROOT_DIR, "config.ini")


def main(video_file, num):
    global conn, cur

    # connect to PostgreSQL database
    db_params = config(filename=CONFIG_INI_FILE, section="postgresql")
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    # load detection model
    model = detection.load_inference_resnet50()

    # fetch areas that will be analyzed
    parking_spots = fetch_parking_spots(num)

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

        # check if parking spots are occuppied every nth frame
        if frame_counter % 75 == 0:
            bboxes = detection.detect_objects(
                model, frame, [3, 4], threshold=0.5)
            
            for x1, y1, x2, y2 in bboxes:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imshow("detected", frame)

        # cv2.imshow("parking lot", frame)
        frame_counter += 1


def fetch_parking_spots(camera_num):
    # get hex locations of parking spots
    query = """SELECT location FROM spots
               WHERE camera_id = %s"""
    cur.execute(query, (camera_num,))
    hex_spots = [r[0] for r in cur.fetchall()]

    # convert to shapely objects
    spots = [wkb.loads(hex_spot, hex=True) for hex_spot in hex_spots]
    return spots


def parse_arguments(argv):
    parser = argparse.ArgumentParser()

    # TODO: Data is supposed to be fetched from
    # live feed, not from a video file.
    parser.add_argument("video_file", type=str,
                        help="path/to/video.mp4")
    parser.add_argument("num", type=int,
                        help="section to which analyze")
    return vars(parser.parse_args())


if __name__ == "__main__":
    main(**parse_arguments(sys.argv[1:]))
