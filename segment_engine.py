import cv2
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import os
from scipy.ndimage import convolve
from skimage.morphology import skeletonize

# custom modules
import resources as res
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction

model_path = res.find('other/best.pt')

detection_model = AutoDetectionModel.from_pretrained(
    model_type='yolov8',
    model_path=model_path,
    confidence_threshold=0.2,
    device='cpu'
)


def get_segmentation_result(helper, img_path):
    result = get_sliced_prediction(
        helper,
        img_path,
        detection_model,
        slice_height=640,
        slice_width=640,
        overlap_height_ratio=0.4,
        overlap_width_ratio=0.4
    )

    return result


def create_binary_from_yolo(result):
    first_mask = result.object_prediction_list[0]
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
                dist = np.sqrt(dx ** 2 + dy ** 2)
                if dist < min_dist:
                    min_dist = dist
                    closest_pixel = (nx, ny)

    return closest_pixel


def find_path(img, x, y, junctions, endpoints):
    if img[x, y] == 0:  # Check if the starting pixel is part of the skeleton
        return []

    def dfs(start_x, start_y, visited):
        if not (0 <= start_x < img.shape[0] and 0 <= start_y < img.shape[1]):
            return []
        if img[start_x, start_y] == 0:
            return []
        if (start_x, start_y) in visited:
            return []
        if is_node(start_x, start_y, junctions):
            return [(start_x, start_y)]
        if is_node(start_x, start_y, endpoints):
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

    path2 = dfs(neighbors[1][0], neighbors[1][1], set([(x, y)]))


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
    # Get the dimensions of the image
    height, width = img.shape[:2]

    # Filter out coordinates that are outside the image bounds
    valid_coords = (coords[:, 0] >= 0) & (coords[:, 0] < height) & \
                   (coords[:, 1] >= 0) & (coords[:, 1] < width)
    filtered_coords = coords[valid_coords]

    # Set the corresponding pixels to white
    img[filtered_coords[:, 0], filtered_coords[:, 1]] = 255

    return img


def remove_mask_from_paint(img, coords):
    # Get the dimensions of the image
    height, width = img.shape[:2]

    # Filter out coordinates that are outside the image bounds
    valid_coords = (coords[:, 0] >= 0) & (coords[:, 0] < height) & \
                   (coords[:, 1] >= 0) & (coords[:, 1] < width)
    filtered_coords = coords[valid_coords]

    # Set the corresponding pixels to white
    img[filtered_coords[:, 0], filtered_coords[:, 1]] = 0

    return img



def build_graph(junctions, endpoints, skel):
    G = nx.Graph()

    # Add junctions and endpoints as nodes
    for point in np.vstack([junctions, endpoints]):
        G.add_node(tuple(point))

    # Helper function to check if a point is within the image bounds
    def is_within_bounds(pos, shape):
        y, x = pos
        return 0 <= y < shape[0] and 0 <= x < shape[1]

    # Helper function to get neighbors
    def get_neighbors(pos):
        y, x = pos
        neighbors = [
            (y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1),
            (y - 1, x - 1), (y - 1, x + 1), (y + 1, x - 1), (y + 1, x + 1)
        ]
        valid_neighbors = [n for n in neighbors if is_within_bounds(n, skel.shape) and skel[n] == 255]
        return valid_neighbors

    # Function to run BFS and add edges
    def add_edges_from_node(start):
        queue = [(start, [start])]
        visited_local = set()

        while queue:
            current, path = queue.pop(0)

            if current != start and current in all_nodes:
                edge = (start, current)
                # Check if the edge already exists to avoid duplicates
                if not G.has_edge(*edge):
                    G.add_edge(*edge, path=path)
                continue

            visited_local.add(current)
            neighbors = get_neighbors(current)

            for neighbor in neighbors:
                if neighbor not in visited_local:
                    new_path = path + [neighbor]
                    queue.append((neighbor, new_path))

    # Combine junctions and endpoints
    all_nodes = set(tuple(p) for p in np.vstack([junctions, endpoints]))

    # Run BFS from each junction and endpoint
    for node in all_nodes:
        add_edges_from_node(node)

    return G


def build_graph_old(junctions, endpoints, skel):
    G = nx.Graph()

    # Add junctions and endpoints as nodes
    for point in np.vstack([junctions, endpoints]):
        G.add_node(tuple(point))

    # Helper function to get neighbors
    def get_neighbors(pos):
        y, x = pos
        neighbors = [
            (y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1),
            (y - 1, x - 1), (y - 1, x + 1), (y + 1, x - 1), (y + 1, x + 1)
        ]
        return [n for n in neighbors if skel[n] == 255]

    # Mark all junctions as visited initially
    visited_junctions = set(tuple(p) for p in junctions)

    for endpoint in endpoints:
        start = tuple(endpoint)
        queue = [start]
        path = [start]
        visited_local = set([start])

        while queue:
            current = queue.pop(0)
            if current != start and (current in visited_junctions or current in set(map(tuple, endpoints))):
                # Found a junction or another endpoint, add the edge
                G.add_edge(start, current, path=path.copy())
                break
            visited_local.add(current)
            neighbors = get_neighbors(current)

            for neighbor in neighbors:
                if neighbor not in visited_local:
                    queue.append(neighbor)
                    path.append(neighbor)

    return G


def segment_lookup_table(graph):
    lookup = {}
    for edge in graph.edges:
        # Retrieve all pixels in this segment
        segment_pixels = get_segment_pixels(edge, graph)

        # Map each pixel to the corresponding segment
        for pixel in segment_pixels:
            lookup[tuple(pixel)] = edge

    return lookup


def get_segment_pixels(segment, graph):
    # Extract the start and end points from the segment
    start, end = segment

    # Retrieve the path from the graph
    path = graph.edges[start, end]['path']

    # If the path is directly stored in the edge attribute
    return path


def find_path_bis(x, y, graph, lookup_table):
    pixel = (x, y)
    segment = lookup_table.get(pixel, None)

    path = get_segment_pixels(segment, graph)

    return path


def visualize_graph(graph, skel):
    # Create a plot
    plt.figure(figsize=(12, 12))

    # Draw the skeleton image as the background
    plt.imshow(skel, cmap='gray')

    # Draw the graph
    pos = {node: (node[1], node[0]) for node in graph.nodes()}  # Adjust position for correct orientation
    nx.draw(graph, pos, node_size=50, node_color='red', edge_color='blue', with_labels=True)

    # Show the plot
    plt.show()


def split_image(image_path, dest_folder, w_train, h_train, overlap, prefix='', save=True):
    # Load the image
    image = cv2.imread(image_path)
    h, w = image.shape[:2]

    # Calculate step size
    step_w = int(w_train * (1 - overlap))
    step_h = int(h_train * (1 - overlap))

    # Initialize list to hold cropped images
    cropped_images = []
    names = []

    # Iterate over the image
    for y in range(0, h, step_h):
        for x in range(0, w, step_w):
            # Crop the image
            crop = image[y:y+h_train, x:x+w_train]
            cropped_images.append(crop)

            name = f"{prefix}_crop_{x}_{y}.png"
            path = os.path.join(dest_folder, name)
            names.append(name)

            if save:
                # Optionally save each crop
                cv2.imwrite(path, crop)

    return cropped_images, names

def convert_bin_mask_to_yolo_txt(mask_image, txt_dest_path, as_box=False, class_index=0):
    if len(mask_image.shape) == 3:
        mask_image = cv2.cvtColor(mask_image, cv2.COLOR_BGR2GRAY)

    if mask_image.dtype != 'uint8':
        mask_image = mask_image.astype('uint8')

    # Find contours
    contours, _ = cv2.findContours(mask_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        print("No contours found.")
        return

    # Image dimensions
    image_height, image_width = mask_image.shape

    # Open file to write annotations
    with open(txt_dest_path, 'w') as file:
        for contour in contours:
            if as_box:
                # Calculate bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Normalize coordinates
                x_center = (x + w / 2) / image_width
                y_center = (y + h / 2) / image_height
                width = w / image_width
                height = h / image_height

                # Write YOLO annotation (assuming object class is 0)
                file.write(f'0 {x_center} {y_center} {width} {height}\n')
            else:
                for contour in contours:
                    # Start each row with the class index
                    file.write(f"{class_index}")

                    for point in contour.squeeze():
                        x, y = point
                        # Normalize coordinates
                        x_normalized = x / image_width
                        y_normalized = y / image_height
                        # Write the normalized coordinates
                        file.write(f" {x_normalized:.4f} {y_normalized:.4f}")

                    # Newline after each contour
                    file.write("\n")