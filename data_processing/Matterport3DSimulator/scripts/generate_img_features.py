#!/usr/bin/env python3

''' Script to precompute image features using a Caffe ResNet CNN, using 36 discretized views
    at each viewpoint in 30 degree increments, and the provided camera WIDTH, HEIGHT 
    and VFOV parameters. '''

import os
import numpy as np
import cv2
import json
import math
import base64
import csv
import sys
import random
csv.field_size_limit(sys.maxsize)


# Caffe and MatterSim need to be on the Python path
sys.path.append('build')
import MatterSim

import caffe

from timer import Timer

import argparse

parser = argparse.ArgumentParser(description='Preprocess Img Features.')
parser.add_argument('--mask_rate', default=0, type=float)
parser.add_argument('--idx', default=0, type=int, help='repeat idx.')
parser.add_argument('--img_dir', default='../../r2r/data/img_features/', type=str)
parser.add_argument('--batch_size', default=4, type=int)
parser.add_argument('--image_feature', default='imagenet', type=str)
parser.add_argument('--proto_file', default='models/ResNet-152-deploy.prototxt', type=str)
parser.add_argument('--mode', type=str, default='all_visible')
parser.add_argument('--foreground_bbox_dir', type=str, default='./bbox/')
parser.add_argument('--all_bbox_dir', type=str, default='./private_bbox/')

args = parser.parse_args()

random.seed(args.idx)

TSV_FIELDNAMES = ['scanId', 'viewpointId', 'image_w','image_h', 'vfov', 'features']
VIEWPOINT_SIZE = 36 # Number of discretized views from one viewpoint
FEATURE_SIZE = 2048
BATCH_SIZE = args.batch_size  # Some fraction of viewpoint size - batch size 4 equals 11GB memory
GPU_ID = 0
PROTO = args.proto_file

if not os.path.isdir(args.img_dir):
    os.mkdir(args.img_dir)
    print(f'{args.img_dir} created!')

if args.image_feature == 'imagenet':
    MODEL = 'models/ResNet-152-model.caffemodel'
elif args.image_feature == 'places365':
    MODEL = 'models/resnet152_places365.caffemodel'
args.outfile_pattern = f'{args.img_dir}/ResNet-152-{args.image_feature}_%s_m%.2f_%d.tsv'

if args.mode == 'foreground':
    bbox_pattern = f'{args.foreground_bbox_dir}/%s_%s.json'
else:
    bbox_pattern = f'{args.all_bbox_dir}/%s_%s.json'
OUTFILE = args.outfile_pattern % (args.mode, args.mask_rate, args.idx)

exclude_object_list = ['wall', 'ceiling', 'floor']

GRAPHS = 'connectivity/'

# Simulator image parameters
WIDTH=640
HEIGHT=480
VFOV=60


def load_viewpointids():
    viewpointIds = []
    with open(GRAPHS+'scans.txt') as f:
        scans = [scan.strip() for scan in f.readlines()]
        for scan in scans:
            with open(GRAPHS+scan+'_connectivity.json')  as j:
                data = json.load(j)
                for item in data:
                    if item['included']:
                        viewpointIds.append((scan, item['image_id']))
    print('Loaded %d viewpoints' % len(viewpointIds))
    return viewpointIds


def _match_names(name, target_list):
    """Check if a name string is in the target list"""
    for s in target_list:
        if s in name:
            return True
    return False


def load_bbox(scanId, viewpointId, mode, env_objects=None):
    """
    Load bbox json.
    Mask out portions of objects.
    Reorganize bbox.
    """
    mask_rate = args.mask_rate
    bbox_file = bbox_pattern % (scanId, viewpointId)
    bbox_info = json.load(open(bbox_file, 'r'))
    rst = [[] for i in range(VIEWPOINT_SIZE)]
    
    if mode == 'foreground':
        bbox_info = bbox_info[viewpointId]
        objects = bbox_info.keys()
        masked_objects = random.sample(objects, int(mask_rate*len(objects)))
        # print(bbox_info, '\n#Total object = %d\n#Masked object = %d\n' % (len(objects), len(masked_objects)), masked_objects)

        for obj_id in masked_objects:
            item = bbox_info[obj_id]
            obj_name = item['name']
            for visible_pos, bbox2d in zip(item['visible_pos'], item['bbox2d']):
                rst[visible_pos].append({
                    'bbox2d': bbox2d,
                    'name': obj_name
                    })
                
    else:
        # collect all the objects in current viewpoint
        raw_objects_in_viewpoint = {}
        for idx in range(VIEWPOINT_SIZE):
            raw_objects_in_viewpoint.update(bbox_info[str(idx)])
        # exclude wall/ceiling/floor
        objects_in_viewpoint = {}
        for obj_id, item in raw_objects_in_viewpoint.items():
            if not _match_names(item['name'], exclude_object_list):
                objects_in_viewpoint[obj_id] = item
        all_obj_id_list = list(objects_in_viewpoint.keys())
        object_name_list = [objects_in_viewpoint[obj_id]['name'] for obj_id in all_obj_id_list]
        
        if mode == 'foreground_controlled_trial':
            foreground_bbox_info = json.load(open(f'{args.foreground_bbox_dir}/{scanId}_{viewpointId}.json'))
            mask_num = int(mask_rate * min(len(foreground_bbox_info[viewpointId]), len(objects_in_viewpoint)))
        else:
            mask_num = int(mask_rate * len(objects_in_viewpoint))
        # print(f'\n\nMask num = {mask_num}\n{object_name_list}\n\n')
        to_be_masked_id_list = random.sample(all_obj_id_list, mask_num)
        
        for idx in range(VIEWPOINT_SIZE):
            current_objects = bbox_info[str(idx)]
            for obj_id, item in current_objects.items():
                if obj_id in to_be_masked_id_list:
                    rst[idx].append(item)

    return rst

                    
def mask_objects(img, to_be_masked_objs_info, scanId, viewpointId, ix):
    img = np.array(img, copy=True)

    for obj_info in to_be_masked_objs_info:
        average = img.mean(axis=0).mean(axis=0)  # fill mask with average color
        s_x, s_y, w, h = obj_info['bbox2d']
        e_x = s_x + w
        e_y = s_y + h
        thickness = -1
        img = cv2.rectangle(img, (s_x, s_y), (e_x, e_y), average, thickness)

    #     # visualize bbox
    #     color = (255, 0, 0) 
    #     thickness = 2
    #     img = cv2.rectangle(img, (s_x, s_y), (e_x, e_y), color, thickness)

    # # save image
    # filename = 'tmp/%s_%s_%d.jpg' % (scanId, viewpointId, ix)
    # cv2.imwrite(filename, img) 
    # print('Written to %s' % filename)

    return img


def transform_img(im):
    ''' Prep opencv 3 channel image for the network '''
    im = np.array(im, copy=True)
    im_orig = im.astype(np.float32, copy=True)
    im_orig -= np.array([[[103.1, 115.9, 123.2]]]) # BGR pixel mean
    blob = np.zeros((1, im.shape[0], im.shape[1], 3), dtype=np.float32)
    blob[0, :, :, :] = im_orig
    blob = blob.transpose((0, 3, 1, 2))
    return blob


def build_tsv():
    # Set up the simulator
    sim = MatterSim.Simulator()
    sim.setCameraResolution(WIDTH, HEIGHT)
    sim.setCameraVFOV(math.radians(VFOV))
    sim.setDiscretizedViewingAngles(True)
    sim.setBatchSize(1)
    sim.initialize()

    # Set up Caffe resnet
    caffe.set_device(GPU_ID)
    caffe.set_mode_gpu()
    net = caffe.Net(PROTO, MODEL, caffe.TEST)
    net.blobs['data'].reshape(BATCH_SIZE, 3, HEIGHT, WIDTH)

    count = 0
    t_render = Timer()
    t_net = Timer()
    print('Image features will be written to %s' % OUTFILE)
    with open(OUTFILE, 'wt') as tsvfile:
        writer = csv.DictWriter(tsvfile, delimiter = '\t', fieldnames = TSV_FIELDNAMES)
        
        # Loop all the viewpoints in the simulator
        viewpointIds = load_viewpointids()
        for scanId,viewpointId in viewpointIds:
            # Load bbox of the objects to be masked
            flip_current = False  # whether to flip current viewpoint or not
            if args.mode == 'flip':
                if random.uniform(0, 1) < args.mask_rate:
                    flip_current = True
            else:
                to_be_masked_object_list = load_bbox(scanId, viewpointId, args.mode)
           
            t_render.tic()
            # Loop all discretized views from this location
            blobs = []
            features = np.empty([VIEWPOINT_SIZE, FEATURE_SIZE], dtype=np.float32)
            flip_current = False  # whether to flip current viewpoint or not
            if args.flip:
                mask_rate = args.mask_rate
                rand = random.uniform(0, 1)
                if rand < mask_rate:
                    flip_current = True
            for ix in range(VIEWPOINT_SIZE):
                if ix == 0:
                    sim.newEpisode([scanId], [viewpointId], [0], [math.radians(-30)])
                elif ix % 12 == 0:
                    sim.makeAction([0], [1.0], [1.0])
                else:
                    sim.makeAction([0], [1.0], [0])

                state = sim.getState()[0]
                assert state.viewIndex == ix
                
                # Transform and save generated image
                if args.mode == 'flip':
                    if flip_current:
                        masked_img = cv2.flip(np.array(state.rgb, copy=True), 1)
                    else:
                        masked_img = np.array(state.rgb, copy=True)
                else:
                    masked_img = mask_objects(state.rgb, to_be_masked_object_list[ix], scanId, viewpointId, ix)
                blobs.append(transform_img(masked_img))

            if flip_current:
                new_blobs = blobs[:12][::-1] + blobs[12:24][::-1] + blobs[24:][::-1]
                blobs = new_blobs

            t_render.toc()
            t_net.tic()

            # Run as many forward passes as necessary
            assert VIEWPOINT_SIZE % BATCH_SIZE == 0
            forward_passes = VIEWPOINT_SIZE // BATCH_SIZE
            ix = 0
            for f in range(forward_passes):
                for n in range(BATCH_SIZE):
                    # Copy image blob to the net
                    net.blobs['data'].data[n, :, :, :] = blobs[ix]
                    ix += 1
                # Forward pass
                output = net.forward()
                features[f*BATCH_SIZE:(f+1)*BATCH_SIZE, :] = net.blobs['pool5'].data[:,:,0,0]
            writer.writerow({
                'scanId': scanId,
                'viewpointId': viewpointId,
                'image_w': WIDTH,
                'image_h': HEIGHT,
                'vfov' : VFOV,
                'features': str(base64.b64encode(features), "utf-8")
            })
            count += 1
            t_net.toc()
            if count % 100 == 0:
                print('Processed %d / %d viewpoints, %.1fs avg render time, %.1fs avg net time, projected %.1f hours' %\
                  (count,len(viewpointIds), t_render.average_time, t_net.average_time, 
                  (t_render.average_time+t_net.average_time)*len(viewpointIds)/3600), flush=True)


def read_tsv(infile):
    # Verify we can read a tsv
    in_data = []
    with open(infile, "rt") as tsv_in_file:
        reader = csv.DictReader(tsv_in_file, delimiter='\t', fieldnames = TSV_FIELDNAMES)
        for item in reader:
            item['scanId'] = item['scanId']
            item['image_h'] = int(item['image_h'])
            item['image_w'] = int(item['image_w'])
            item['vfov'] = int(item['vfov'])
            item['features'] = np.frombuffer(base64.b64decode(item['features']),
                    dtype=np.float32).reshape((VIEWPOINT_SIZE, FEATURE_SIZE))
            in_data.append(item)
    return in_data


if __name__ == "__main__":

    build_tsv()
    data = read_tsv(OUTFILE)
    print('Completed %d viewpoints' % len(data))

