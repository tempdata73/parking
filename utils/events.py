import cv2
import numpy as np


# Constants
IDX = 0


def fetch_points_callback(event, x, y, flags, param):
    global IDX

    if event == cv2.EVENT_LBUTTONDOWN:
        param[IDX].append((x, y))

    elif event == cv2.EVENT_RBUTTONDOWN:
        IDX += 1
        param[IDX] = []


def select_area(frame):
    # initialize data
    polygons = {IDX: []}
    window_name = "Select area"

    # set callback
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(
        window_name, fetch_points_callback, param=polygons)
    
    # fetch points
    cv2.imshow(window_name, frame)
    cv2.waitKey(0) & 0xFF
    cv2.destroyWindow(window_name)

    # polygon must have at least three points
    coords = list(polygons.values())
    for pts in coords:
        assert len(pts) > 2, "Polygon must have at least 3 points"

    return coords


def sort2cyclic(pts):   
    # TODO: add documentation; basic idea is to order
    # the polygons in a cyclic fashion so as to make
    # them closed polygons.
    corner_angles = []
    pts = np.asarray(pts)
    centroid = np.mean(pts, axis=0)
        
    for x, y in pts:
        theta = np.arctan2(y - centroid[1], x - centroid[0])
        corner_angles.append((x, y, theta))

    corner_angles.sort(key=lambda k: k[2])
    cyclic = [(x, y) for x, y, theta in corner_angles]
    # Polygon must be closed as well
    cyclic.append(cyclic[0])

    return cyclic
