import pickle

import cv2   
import numpy as np   
import glob
import os


def bounding_boxes_detection(image_path, mask_set_path, method, save_masks, idx):
    """
    This function detects the bounding boxes of the text in all the images of a specific folder

    :param image_path: path of the images
    :param mask_set_path: path where the masks will be saved
    :param method: 1 for color segmentation and 2 for morphology operations
    :param save_masks: bool indicating if the masks need to be saved
    :param idx: int containing the index of the image
    :return: list of bounding boxes from first image to last image. Each image contains a maximum of 2 bounding boxes.

        [[[first_bounding_box_of_first_image],[second_bounding_box_of_second_image]], [[first_bounding_box_of_second_image]], ...]

    Each bounding box has the following int values:

        [lowest_pixel_x, lowest_pixel_y, highest_pixel_x, highest_pixel_y] 
    
    """

    # Create the empty list to store the bounding boxes coordinates
    boxes = []
    # Read every image
    image = cv2.imread(image_path)

    #----------------------------------   METHOD 1   ----------------------------------------------------------
    """
    Method 1: text detection based on color segmentation using saturation
    """
    if method == 1:

        saturation_threshold = 20

        # Color image segmentation to create binary image (255 white: high possibility of text; 0 black: no text)
        im_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        _, s, _ = cv2.split(im_hsv)

        image_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        image_grey[s < saturation_threshold] = 255
        image_grey[image_grey != 255] = 0

        # Cleaning image using morphological opening filter
        opening_kernel = np.ones((5, 5), np.uint8)/9
        text_mask = cv2.morphologyEx(image_grey, cv2.MORPH_OPEN, opening_kernel, iterations=1)

    #----------------------------------   METHOD 2   ----------------------------------------------------------
    """
    Method 2: text detection based on morphology operations
    """

    if method == 2:

        # Define grayscale image
        im_yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
        im_y, _, _ = cv2.split(im_yuv)

        # Define kernel sizes
        kernel = np.ones((3, 3), np.float32)/9

        # Difference between erosion and dilation images
        y_dilation = cv2.morphologyEx(im_y, cv2.MORPH_DILATE, kernel, iterations=1)
        y_erosion = cv2.morphologyEx(im_y, cv2.MORPH_ERODE, kernel, iterations=1)

        difference_image = y_erosion - y_dilation

        # Grow contrast areas found
        growing_image = cv2.morphologyEx(difference_image, cv2.MORPH_ERODE, kernel, iterations=1)

        # Low pass filter to smooth out the result
        blurry_image = cv2.filter2D(growing_image, -1, kernel)

        # Thresholding the image to make a binary image
        ret, binary_image = cv2.threshold(blurry_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        inverted_binary_image = cv2.bitwise_not(binary_image)

        # Clean small white pixels areas outside text using closing filter
        #text_mask = cv2.morphologyEx(inverted_binary_image, cv2.MORPH_OPEN, kernel, iterations = 1)

        text_mask = inverted_binary_image


    #------------------------------   FINDING AND CHOOSING CONTOURS OF THE BINARY MASK   ---------------------------------------

    # Finding contours of the white areas of the images (high possibility of text)
    contours, _ = cv2.findContours(text_mask,  cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]

    # Initialize parameters
    largest_area, second_largest_area, x_box_1, y_box_1, w_box_1, h_box_1, x_box_2, y_box_2, w_box_2, h_box_2 = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    image_width = text_mask.shape[0]

    # From all the contours found, pick only the ones with rectangular shape and large area
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)

        if (w / h > 2) & (w / h < 12) & (w > (0.1 * image_width)) & (area > second_largest_area):

            if area > largest_area:
                x_box_2, y_box_2, w_box_2, h_box_2 = x_box_1, y_box_1, w_box_1, h_box_1
                x_box_1, y_box_1, w_box_1, h_box_1 = x, y, w, h
                second_largest_area = largest_area
                largest_area = area

            else:
                x_box_2, y_box_2, w_box_2, h_box_2 = x, y, w, h
                second_largest_area = area

    # cv2.rectangle(image, (x_box_1, y_box_1), (x_box_1 + w_box_1 - 1, y_box_1 + h_box_1 - 1), 255, 2)
    # cv2.rectangle(image, (x_box_2, y_box_2), (x_box_2 + w_box_2 - 1, y_box_2 + h_box_2 - 1), 255, 2)

    # Append the corners of the bounding boxes to the boxes list

    if (x_box_2 == y_box_2 == 0) | (image_path == 'images/qst1_w3_denoised/'):
        box = [[x_box_1, y_box_1, x_box_1 + w_box_1, y_box_1 + h_box_1]]
        boxes.append(box)
    elif x_box_1 < x_box_2:
        box = [[x_box_1, y_box_1, x_box_1 + w_box_1, y_box_1 + h_box_1], [x_box_2, y_box_2, x_box_2 + w_box_2, y_box_2 + h_box_2]]
        boxes.append(box)
    else:
        box = [[x_box_2, y_box_2, x_box_2 + w_box_2, y_box_2 + h_box_2], [x_box_1, y_box_1, x_box_1 + w_box_1, y_box_1 + h_box_1]]
        boxes.append(box)

    if save_masks:
        cv2.imwrite(mask_set_path + str(idx) + '.png', text_mask)

    return boxes


def bounding_boxes_evaluation(boxA, boxB):
    """
    This function evaluates the accuracy of the result bounding boxes by calculating the parameter intersection over
    Union (IoU)

    :param boxA: Ground Truth bounding boxes
    :param boxB: bounding boxes detected in the images

    :return: float with IoU parameter

    """

    iou_total = []

    for idx in range(len(boxA)):
        for subidx in range(len(boxA[idx])):
            if len(boxB[idx]) > subidx:
                
                # determine the (x, y)-coordinates of the intersection rectangle
                xA = max(boxA[idx][subidx][0], boxB[idx][subidx][0])
                yA = max(boxA[idx][subidx][1], boxB[idx][subidx][1])
                xB = min(boxA[idx][subidx][2], boxB[idx][subidx][2])
                yB = min(boxA[idx][subidx][3], boxB[idx][subidx][3])

                # compute the area of intersection rectangle
                interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)

                # compute the area of both the prediction and ground-truth
                # rectangles
                boxAArea = (boxA[idx][subidx][2] - boxA[idx][subidx][0] + 1) * (boxA[idx][subidx][3] - boxA[idx][subidx][1] + 1)
                boxBArea = (boxB[idx][subidx][2] - boxB[idx][subidx][0] + 1) * (boxB[idx][subidx][3] - boxB[idx][subidx][1] + 1)

                # compute the intersection over union by taking the intersection
                # area and dividing it by the sum of prediction + ground-truth
                # areas - the interesection area
                iou = interArea / float(boxAArea + boxBArea - interArea)
                iou_total.append(iou)

            else: 
                iou_total.append(0)

    iou_mean = sum(iou_total) / len(iou_total)

    return iou_mean
