import glob
import os
import random
from typing import List

import torch
import torchvision
from ffcv.fields.decoders import IntDecoder, NDArrayDecoder
from ffcv.fields.rgb_image import (
    CenterCropRGBImageDecoder,
    RandomResizedCropRGBImageDecoder,
)
from ffcv.loader import Loader, OrderOption
from ffcv.pipeline.operation import Operation
from ffcv.transforms import (
    Convert,
    ImageMixup,
    LabelMixup,
    RandomHorizontalFlip,
    ToDevice,
    ToTensor,
    ToTorchImage,
)
from ffcv.transforms.common import Squeeze

from .data_stats import *


# Define an ffcv dataloader
def get_loader(
    dataset,
    bs,
    mode,
    augment,
    dev,
    data_resolution=None,
    crop_resolution=None,
    crop_ratio=(0.75, 1.3333333333333333),
    crop_scale=(0.08, 1.0),
    num_samples=None,
    dtype=torch.float32,
    mixup=None,
    data_path='./beton',
):
    mode_name = MODE_DICT[dataset] if mode != 'train' else mode
    os_cache = OS_CACHED_DICT[dataset]

    if data_resolution is None:
        data_resolution = DEFAULT_RES_DICT[dataset]
    if crop_resolution is None:
        crop_resolution = data_resolution

    real = '' if dataset != 'imagenet_real' or mode == 'train' else 'real_'
    sub_sampled = '' if num_samples is None or num_samples == SAMPLE_DICT[dataset] else '_ntrain_' + str(num_samples)

    beton_path = os.path.join(
        data_path,
        DATA_DICT[dataset],
        real + f'{mode_name}_{data_resolution}' + sub_sampled + '.beton',
    )

    print(f'Loading {beton_path}')

    mean = MEAN_DICT[dataset]
    std = STD_DICT[dataset]

    label_pipeline: List[Operation] = [IntDecoder()]

    if augment:
        image_pipeline: List[Operation] = [
            RandomResizedCropRGBImageDecoder((crop_resolution, crop_resolution), ratio=crop_ratio, scale=crop_scale),
            RandomHorizontalFlip(),
        ]
    else:
        image_pipeline: List[Operation] = [
            CenterCropRGBImageDecoder(output_size=(crop_resolution, crop_resolution), ratio=1)
        ]

    # Add image transforms and normalization
    if mode == 'train' and augment and mixup > 0:
        image_pipeline.extend([ImageMixup(alpha=mixup, same_lambda=True)])
        label_pipeline.extend([LabelMixup(alpha=mixup, same_lambda=True)])

    label_pipeline.extend([ToTensor(), ToDevice(dev, non_blocking=True), Squeeze()])

    image_pipeline.extend(
        [
            ToTensor(),
            ToDevice(dev, non_blocking=True),
            ToTorchImage(),
            Convert(dtype),
            torchvision.transforms.Normalize(mean, std),
        ]
    )

    if mode == 'train':
        num_samples = SAMPLE_DICT[dataset] if num_samples is None else num_samples

    return Loader(
        beton_path,
        batch_size=bs,
        num_workers=4,
        order=OrderOption.QUASI_RANDOM if mode == 'train' else OrderOption.SEQUENTIAL,
        drop_last=(mode == 'train'),
        pipelines={'image': image_pipeline, 'label': label_pipeline},
        os_cache=os_cache,
        indices=None,
    )