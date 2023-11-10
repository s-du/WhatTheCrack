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

def create_binary_image(result, output_folder):
    first_mask = result.object_prediction_list[0]
    print(first_mask)
    mask = np.asarray(first_mask.mask.bool_mask)
    combined_mask = mask


    for r in result.object_prediction_list:
        mask = np.asarray(r.mask.bool_mask)
        combined_mask = np.logical_or(combined_mask, mask)

    # Now convert the combined mask to a binary image (uint8)
    binary_image = (combined_mask * 255).astype(np.uint8)

    # Convert the binary image to a PIL Image and save it
    image = Image.fromarray(binary_image)
    output_binary_mask = os.path.join(output_folder, 'combined_binary_mask.png')
    image.save(output_binary_mask)

    # Create an empty 3-channel image with the same dimensions as the binary image
    height, width = binary_image.shape
    color_image = np.zeros((height, width, 3), dtype=np.uint8)

    # Set the blue channel
    color_image[:, :, 2] = binary_image

    # Now color_image is a blue version of your binary image
    image = Image.fromarray(color_image)
    output_color_mask = os.path.join(output_folder, 'combined_color_mask.png')
    image.save(output_color_mask)

    # Skeletonize the image
    skeleton = skeletonize(binary_image)

    # Count the non-zero pixels in the skeletonized image
    crack_length = np.count_nonzero(skeleton)

    # Convert the skeletonized image to uint8 to save it
    skeleton_image = (skeleton * 255).astype(np.uint8)

    # Convert the skeletonized binary image to a PIL Image and save it
    image = Image.fromarray(skeleton_image)
    output_skeleton = os.path.join(output_folder, 'skeleton_image.png')
    image.save(output_skeleton)

    color_image = np.zeros((height, width, 3), dtype=np.uint8)

    # Set the blue channel
    color_image[:, :, 0] = skeleton_image

    # Now color_image is a blue version of your binary image
    image = Image.fromarray(color_image)
    output_skel_color = os.path.join(output_folder, 'skeleton_color.png')
    image.save(output_skel_color)

    return crack_length, output_binary_mask, output_color_mask, output_skeleton, output_skel_color


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

def is_node(x, y, junctions, endpoints):
    return (x, y) in junctions or (x, y) in endpoints

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

def find_path(img, x, y, junctions, endpoints, radius=100):
    # Find the closest white pixel within the given radius
    start_pixel = find_closest_white_pixel(img, x, y, radius)
    if start_pixel is None:
        return []

    x, y = start_pixel
    visited = set()
    path = []

    def dfs(x, y):
        if not is_valid_pixel(x, y, img.shape) or img[x, y] == 0 or (x, y) in visited:
            return
        visited.add((x, y))
        path.append((x, y))

        if is_node(x, y, junctions, endpoints):
            return

        # 8-neighborhood
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    dfs(x + dx, y + dy)

    dfs(x, y)
    return path

def highlight_path(img_shape, path):
    # Create a black image of the same size as the original image
    highlighted_img = np.zeros(img_shape, dtype=np.uint8)

    # Set the pixels along the path to white
    for x, y in path:
        highlighted_img[x, y] = 255

    return highlighted_img