import argparse
import os
import torch

class Param:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="")

        # General
        self.parser.add_argument('--test_only', type=int, default=0, help='fast mode for testing')

        self.parser.add_argument('--iters', type=int, default=300000, help='training iterations')
        self.parser.add_argument('--name', type=str, default='default', help='experiment id')
        self.parser.add_argument('--vlnbert', type=str, default='oscar', help='oscar or prevalent')
        self.parser.add_argument('--train', type=str, default='listener')
        self.parser.add_argument('--description', type=str, default='no description\n')

        # Data preparation
        self.parser.add_argument('--maxInput', type=int, default=80, help="max input instruction")
        self.parser.add_argument('--maxAction', type=int, default=15, help='Max Action sequence')
        self.parser.add_argument('--batchSize', type=int, default=8)
        self.parser.add_argument('--ignoreid', type=int, default=-100)
        self.parser.add_argument('--feature_size', type=int, default=2048)
        self.parser.add_argument("--loadOptim",action="store_const", default=False, const=True)

        # Load the model from
        self.parser.add_argument("--load", default=None, help='path of the trained model')

        # Augmented Paths from
        self.parser.add_argument("--aug", default=None)

        # Listener Model Config
        self.parser.add_argument("--zeroInit", dest='zero_init', action='store_const', default=False, const=True)
        self.parser.add_argument("--mlWeight", dest='ml_weight', type=float, default=0.20)
        self.parser.add_argument("--teacherWeight", dest='teacher_weight', type=float, default=1.)
        self.parser.add_argument("--features", type=str, default='places365')

        # Dropout Param
        self.parser.add_argument('--dropout', type=float, default=0.5)
        self.parser.add_argument('--featdropout', type=float, default=0.3)

        # Submision configuration
        self.parser.add_argument("--submit", type=int, default=0)

        # Training Configurations
        self.parser.add_argument('--optim', type=str, default='rms')    # rms, adam
        self.parser.add_argument('--lr', type=float, default=0.00001, help="the learning rate")
        self.parser.add_argument('--decay', dest='weight_decay', type=float, default=0.)
        self.parser.add_argument('--feedback', type=str, default='sample',
                            help='How to choose next position, one of ``teacher``, ``sample`` and ``argmax``')
        self.parser.add_argument('--teacher', type=str, default='final',
                            help="How to get supervision. one of ``next`` and ``final`` ")
        self.parser.add_argument('--epsilon', type=float, default=0.1)

        # Model hyper params:
        self.parser.add_argument("--angleFeatSize", dest="angle_feat_size", type=int, default=4)

        # A2C
        self.parser.add_argument("--gamma", default=0.9, type=float)
        self.parser.add_argument("--normalize", dest="normalize_loss", default="total", type=str, help='batch or total')
        
        # Diagnose-VLN
        self.parser.add_argument('--dataset', default='R2R', type=str)
        self.parser.add_argument('--setting', default='default', type=str)
        self.parser.add_argument('--rate', default=1.0, type=float)
        self.parser.add_argument('--repeat_time', default=5, type=int)
        self.parser.add_argument('--repeat_idx', default=0, type=int)
        self.parser.add_argument('--reset_img_feat', default=0, type=int)
        self.parser.add_argument('--data_dir', default='../../data/')
        self.parser.add_argument('--img_dir', default='../../data/img_features', type=str)
        self.parser.add_argument('--img_feat_pattern', default='ResNet-152-imagenet_%s_m%.2f_%d.tsv', type=str)
        self.parser.add_argument('--img_feat_mode', default='foreground', type=str)
        self.parser.add_argument('--val_log_dir', default='../../log/', type=str)
        self.parser.add_argument('--proto_file', default='../../../data_processing/Matterport3DSimulator/models/deploy_resnet152_places365.prototxt', type=str)
        self.parser.add_argument('--caffe_model', default='../../../data_processing/Matterport3DSimulator/models/resnet152_places365.caffemodel', type=str)
        self.parser.add_argument('--bbox_pattern', default='../../../data_processing/Matterport3DSimulator/private_bbox/%s_%s.json', type=str)
        self.parser.add_argument('--matterport_scan_dir', default='../../../data_processing/Matterport3DSimulator/data/v1/scans/')
        self.parser.add_argument('--feat_batch_size', default=6, type=int)

        self.args = self.parser.parse_args()

        if self.args.optim == 'rms':
            print("Optimizer: Using RMSProp")
            self.args.optimizer = torch.optim.RMSprop
        elif self.args.optim == 'adam':
            print("Optimizer: Using Adam")
            self.args.optimizer = torch.optim.Adam
        elif self.args.optim == 'adamW':
            print("Optimizer: Using AdamW")
            self.args.optimizer = torch.optim.AdamW
        elif self.args.optim == 'sgd':
            print("Optimizer: sgd")
            self.args.optimizer = torch.optim.SGD
        else:
            assert False

param = Param()
args = param.args

args.description = args.name
args.log_dir = 'snap/%s' % args.name

if not os.path.exists(args.val_log_dir):
    os.makedirs(args.val_log_dir)
