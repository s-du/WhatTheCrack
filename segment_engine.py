from PySide6.QtGui import QImage, QColor, QPainter

from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from skimage.morphology import skeletonize
from scipy.ndimage import convolve
from PIL import Image
import numpy as np
import os
import resources as res
import cv2

model_path = res.find('other/best.pt')

detection_model = AutoDetectionModel.from_pretrained(
    model_type='yolov8',
    model_path=model_path,
    confidence_threshold=0.2,
    device='cpu'
)

def get_segmentation_result(img_path):
    result = get_sliced_prediction(
        img_path,
        detection_model,
        slice_height = 640,
        slice_width = 640,
        overlap_height_ratio = 0.4,
        overlap_width_ratio = 0.4
    )

    return result

def create_binary_from_yolo(result):
    first_mask = result.object_prediction_list[0]
    print(first_mask)
    mask = np.asarray(first_mask.mask.bool_mask)
    combined_mask = mask


    for r in result.object_prediction_list:
        mask = np.asarray(r.mask.bool_mask)
        combined_mask = np.logical_or(combined_mask, mask)

    # Now convert the combined mask to a binary image (uint8)
    binary_image = (combined_mask * 255).astype(np.uint8)

    return binary_image

def binary_to_color_mask(binary_image):
    # Create an empty 3-channel image with the same dimensions as the binary image
    height, width = binary_image.shape
    color_image = np.zeros((height, width, 3), dtype=np.uint8)

    # Set the blue channel
    color_image[:, :, 2] = binary_image

    # Now color_image is a blue version of your binary image
    return color_image

def binary_to_skeleton(binary_image):
    # Skeletonize the image
    skeleton = skeletonize(binary_image)

    # Count the non-zero pixels in the skeletonized image
    crack_length = np.count_nonzero(skeleton)

    # Convert the skeletonized image to uint8 to save it
    skeleton_image = (skeleton * 255).astype(np.uint8)

    return skeleton_image


def find_junctions_endpoints(skel_path):
    img = cv2.imread(skel_path, 0)
    _, skel = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    # Kernel for convolution
    kernel = np.array([[1, 1, 1], [1, 10, 1], [1, 1, 1]], dtype=np.uint8)

    # Apply convolution
    filtered = convolve(skel // 255, kernel, mode='constant', cval=1)

    # Junctions have a value greater than 12
    # Endpoints have a value of exactly 11
    junctions = np.argwhere(filtered > 12)
    endpoints = np.argwhere(filtered == 11)

    return junctions, endpoints

def is_valid_pixel(x, y, img_shape):
    return 0 <= x < img_shape[0] and 0 <= y < img_shape[1]

def is_node(x, y, nodes_array):
    return any((nodes_array == [x, y]).all(1))

def find_closest_white_pixel(img, x, y, radius):
    min_dist = float('inf')
    closest_pixel = None

    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            nx, ny = x + dx, y + dy
            if is_valid_pixel(nx, ny, img.shape) and img[nx, ny] == 255:
                dist = np.sqrt(dx**2 + dy**2)
                if dist < min_dist:
                    min_dist = dist
                    closest_pixel = (nx, ny)

    return closest_pixel

def find_path(img, x, y, junctions, endpoints):
    if img[x, y] == 0:  # Check if the starting pixel is part of the skeleton
        return []

    def dfs(start_x, start_y, visited):
        print(start_x, start_y)
        if not (0 <= start_x < img.shape[0] and 0 <= start_y < img.shape[1]):
            return []
        if img[start_x, start_y] == 0:
            print('Zero!')
            return []
        if (start_x, start_y) in visited:
            print('Visited!')
            return []
        if is_node(start_x, start_y, junctions):
            print('reach junction!___________________________')
            return [(start_x, start_y)]
        if is_node(start_x, start_y, endpoints):
            print('reach end point!___________________________')
            return [(start_x, start_y)]

        visited.add((start_x, start_y))
        path = [(start_x, start_y)]

        # 8-neighborhood
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    nx, ny = start_x + dx, start_y + dy
                    if (nx, ny) not in visited:
                        next_path = dfs(nx, ny, visited)
                        if next_path:
                            return path + next_path
        return path



    # Find the immediate neighbors that are part of the skeleton
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx != 0 or dy != 0:
                nx, ny = x + dx, y + dy
                if 0 <= nx < img.shape[0] and 0 <= ny < img.shape[1] and img[nx, ny] != 0:
                    neighbors.append((nx, ny))

    # If less than two neighbors, cannot determine two directions
    if len(neighbors) < 2:
        return []

    # Perform DFS in two different directions
    path1 = dfs(neighbors[0][0], neighbors[0][1], set([(x, y)]))
    print(path1)
    path2 = dfs(neighbors[1][0], neighbors[1][1], set([(x, y)]))
    print(path2)

    # Combine the paths with the starting point in the middle
    combined_path = path1[::-1] + [(x, y)] + path2

    return combined_path

def highlight_path(img_shape, path):
    # Create a black image of the same size as the original image
    highlighted_img = np.zeros(img_shape, dtype=np.uint8)

    # Set the pixels along the path to white
    for x, y in path:
        highlighted_img[x, y] = 255

    return highlighted_img

def create_mask_from_paint(img, coords):
    # Set the corresponding pixels to white
    img[coords[:, 0], coords[:, 1]] = 255

    return img

def remove_mask_from_paint(img, coords):
    # Set the corresponding pixels to white
    img[coords[:, 0], coords[:, 1]] = 0

    return img
