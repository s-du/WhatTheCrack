from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from skimage.morphology import skeletonize
from PIL import Image
import numpy as np
import os
import resources as res

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
