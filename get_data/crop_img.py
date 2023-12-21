import os
import operator
import numpy as np
import SimpleITK as sitk
from data_util import get_arr_from_nrrd, get_bbox, generate_sitk_obj_from_npy_array
#from scipy.ndimage import sobel, generic_gradient_magnitude
from scipy import ndimage
from SimpleITK.extra import GetArrayFromImage
from scipy import ndimage
import cv2
import matplotlib as plt


def crop_top(patient_id, img, seg, crop_shape, return_type, output_img_dir, 
             output_seg_dir, image_format):

    """
    Will crop around the center of bbox of label.
    Args:
        dataset (str): Name of dataset.
        patient_id (str): Unique patient id.
        path_to_image_nrrd (str): Path to image nrrd file.
        path_to_label_nrrd (str): Path to label nrrd file.
        crop_shape (list) shape to save cropped image  (x, y, z)
        return_type (str): Either 'sitk_object' or 'numpy_array'.
        output_folder_image (str) path to folder to save image nrrd
        output_folder_label (str) path to folder to save label nrrd
    Returns:
        Either a sitk image object or a numpy array derived from it (depending on 'return_type') of both image and label.
    Raises:
        Exception if an error occurs.
    """
    
    # get image, arr, and spacing
    #image_object = sitk.ReadImage(img_dir)
    image_arr = sitk.GetArrayFromImage(img)
    image_origin = img.GetOrigin()
    #label_object = sitk.ReadImage(seg_dir)
    label_arr = sitk.GetArrayFromImage(seg)
    label_origin = seg.GetOrigin()
    #assert image_arr.shape==label_arr.shape, "image & label shape do not match!"
    #print('max seg value:', np.max(label_arr))    
    # get center. considers all blobs
    bbox = get_bbox(label_arr)
    # returns center point of the label array bounding box
    Z, Y, X = int(bbox[9]), int(bbox[10]), int(bbox[11]) 
    #print('Original Centroid: ', X, Y, Z)
    
    #find origin translation from label to image
    #print('image origin: ', image_origin, 'label origin: ', label_origin)
    origin_dif = tuple(np.subtract(label_origin, image_origin).astype(int))
    #print('origin difference: ', origin_dif)
    
    X_shift, Y_shift, Z_shift = tuple(np.add((X, Y, Z), np.divide(origin_dif, (1, 1, 3)).astype(int)))
    #print('Centroid shifted:', X_shift, Y_shift, Z_shift) 
    c, y, x = image_arr.shape
    
    ## Get center of mass to center the crop in Y plane
    mask_arr = np.copy(image_arr) 
    mask_arr[mask_arr > -500] = 1
    mask_arr[mask_arr <= -500] = 0
    mask_arr[mask_arr >= -500] = 1 
    #print('mask_arr min and max:', np.amin(mask_arr), np.amax(mask_arr))
    centermass = ndimage.measurements.center_of_mass(mask_arr) # z,x,y   
    cpoint = c - crop_shape[2]//2
    #print('cpoint, ', cpoint)
    centermass = ndimage.measurements.center_of_mass(mask_arr[cpoint, :, :])   
    #print('center of mass: ', centermass)
    startx = int(centermass[0] - crop_shape[0]//2)
    starty = int(centermass[1] - crop_shape[1]//2)      
    #startx = x//2 - crop_shape[0]//2       
    #starty = y//2 - crop_shape[1]//2
    startz = int(c - crop_shape[2])
    #print('start X, Y, Z: ', startx, starty, startz)
     
    #---cut bottom slices---
    image_arr = image_arr[30:, :, :]
    label_arr = label_arr[30:, :, :]
    
    #-----normalize CT data signals-------
    norm_type = 'np_clip'
    #image_arr[image_arr <= -1024] = -1024
    ## strip skull, skull UHI = ~700
    #image_arr[image_arr > 700] = 0
    ## normalize UHI to 0 - 1, all signlas outside of [0, 1] will be 0;
    if norm_type == 'np_interp':
        image_arr = np.interp(image_arr, [-200, 200], [0, 1])
    elif norm_type == 'np_clip':
        image_arr = np.clip(image_arr, a_min=-175, a_max=275)
        MAX, MIN = image_arr.max(), image_arr.min()
        image_arr = (image_arr - MIN) / (MAX - MIN)

    # crop and pad array
    if startz < 0:
        image_arr = np.pad(
            image_arr,
            ((abs(startz)//2, abs(startz)//2), (0, 0), (0, 0)), 
            'constant', 
            constant_values=-1024)
        label_arr = np.pad(
            label_arr,
            ((abs(startz)//2, abs(startz)//2), (0, 0), (0, 0)), 
            'constant', 
            constant_values=0)
        image_arr_crop = image_arr[0:crop_shape[2], starty:starty+crop_shape[1], startx:startx+crop_shape[0]]
        label_arr_crop = label_arr[0:crop_shape[2], starty:starty+crop_shape[1], startx:startx+crop_shape[0]]
    else:
        image_arr_crop = image_arr[0:crop_shape[2], starty:starty+crop_shape[1], startx:startx+crop_shape[0]]
        label_arr_crop = label_arr[0:crop_shape[2], starty:starty+crop_shape[1], startx:startx+crop_shape[0]]
    
    # save nrrd
    output_img = output_img_dir + '/' + patient_id + '.' + image_format
    output_seg = output_seg_dir + '/' + patient_id + '.' + image_format
    # save image
    img_sitk = sitk.GetImageFromArray(image_arr_crop)
    img_sitk.SetSpacing(img.GetSpacing())
    img_sitk.SetOrigin(img.GetOrigin())
    writer = sitk.ImageFileWriter()
    writer.SetFileName(output_img)
    writer.SetUseCompression(True)
    writer.Execute(img_sitk)
    # save label
    seg_sitk = sitk.GetImageFromArray(label_arr_crop)
    seg_sitk.SetSpacing(seg.GetSpacing())
    seg_sitk.SetOrigin(seg.GetOrigin())
    writer = sitk.ImageFileWriter()
    writer.SetFileName(output_seg)
    writer.SetUseCompression(True)
    writer.Execute(seg_sitk)

    
def crop_top_image_only(patient_id, img, crop_shape, return_type, output_dir, image_format):
    """
    Will center the image and crop top of image after it has been registered.
    Args:
        dataset (str): Name of dataset.
        patient_id (str): Unique patient id.
        path_to_image_nrrd (str): Path to image nrrd file.
        path_to_label_nrrd (str): Path to label nrrd file.
        crop_shape (list) shape to save cropped image  (x, y, z)
        return_type (str): Either 'sitk_object' or 'numpy_array'.
        output_folder_image (str) path to folder to save image nrrd
        output_folder_label (str) path to folder to save label nrrd
    Returns:
        Either a sitk image object or a numpy array derived from it (depending on 'return_type') of both image and label.
    Raises:
        Exception if an error occurs.
    """
    # get image, arr, and spacing
    image_arr = sitk.GetArrayFromImage(img)

    #print("image_arr shape: ", image_arr.shape)
    c, y, x = image_arr.shape
    ## Get center of mass to center the crop in Y plane
    mask_arr = np.copy(image_arr) 
    mask_arr[mask_arr > -500] = 1
    mask_arr[mask_arr <= -500] = 0
    mask_arr[mask_arr >= -500] = 1 
    #print("mask_arr min and max:", np.amin(mask_arr), np.amax(mask_arr))
    centermass = ndimage.measurements.center_of_mass(mask_arr) # z,x,y   
    cpoint = c - crop_shape[2]//2
    #print("cpoint, ", cpoint)
    centermass = ndimage.measurements.center_of_mass(mask_arr[cpoint, :, :])   
    #print("center of mass: ", centermass)
    startx = int(centermass[0] - crop_shape[0]//2)
    starty = int(centermass[1] - crop_shape[1]//2) - 40     
    #startx = x//2 - crop_shape[0]//2       
    #starty = y//2 - crop_shape[1]//2
    startz = int(c - crop_shape[2])
    #print("start X, Y, Z: ", startx, starty, startz)
    
    # cut bottom slices
    image_arr = image_arr[30:, :, :]
    #-----normalize CT data signals-------
    norm_type = 'np_clip'
    image_arr[image_arr <= -1024] = -1024
    ## strip skull, skull UHI = ~700
    image_arr[image_arr > 700] = 0
    ## normalize UHI to 0 - 1, all signlas outside of [0, 1] will be 0;
    if norm_type == 'np_interp':
        image_arr = np.interp(image_arr, [-200, 200], [0, 1])
    elif norm_type == 'np_clip':
        #image_arr = np.clip(image_arr, a_min=-200, a_max=200)
        image_arr = np.clip(image_arr, a_min=-175, a_max=275)
        MAX, MIN = image_arr.max(), image_arr.min()
        image_arr = (image_arr - MIN) / (MAX - MIN)

    if startz < 0:
        image_arr = np.pad(
            image_arr, 
            ((abs(startz)//2, abs(startz)//2), (0, 0), (0, 0)), 
            'constant', 
            constant_values=-1024)
        image_arr_crop = image_arr[0:crop_shape[2], starty:starty + crop_shape[1], startx:startx + crop_shape[0]]
    else:
        image_arr_crop = image_arr[0:crop_shape[2], starty:starty + crop_shape[1], startx:startx + crop_shape[0]]
    if image_arr_crop.shape[0] < crop_shape[2]:
        print("initial cropped image shape too small:", image_arr_crop.shape)
        print(crop_shape[2], image_arr_crop.shape[0])
        image_arr_crop = np.pad(
            image_arr_crop,
            ((int(crop_shape[2] - image_arr_crop.shape[0]), 0), (0,0), (0,0)),
            'constant',
            constant_values=-1024)
        print("padded size: ", image_arr_crop.shape)
    #print('Returning bottom rows')
    save_dir = output_dir + '/' + patient_id + '.' + image_format
    new_sitk_object = sitk.GetImageFromArray(image_arr_crop)
    new_sitk_object.SetSpacing(img.GetSpacing())
    new_sitk_object.SetOrigin(img.GetOrigin())
    writer = sitk.ImageFileWriter()
    writer.SetFileName(save_dir)
    writer.SetUseCompression(True)
    writer.Execute(new_sitk_object)


def crop_full_body(img, z):
    
    img_arr = sitk.GetArrayFromImage(img)
    img_arr = img_arr[z:img.GetSize()[2], :, :]
    new_img = sitk.GetImageFromArray(img_arr)
    new_img.SetSpacing(img.GetSpacing())
    new_img.SetOrigin(img.GetOrigin())
    
    return new_img

