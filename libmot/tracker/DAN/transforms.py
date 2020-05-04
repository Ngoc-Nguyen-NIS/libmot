# -*- coding: utf-8 -*-
# Author : HuangPiao
# Email  : huangpiao2985@163.com
# Date   : 18/4/2020
# referring to https://github.com/shijieS/SST/blob/master/utils/augmentations.py

import torch
from torchvision import transforms
import cv2
import numpy as np
import types
from numpy import random
from libmot.utils import iou


class Compose(object):
    """Composes several augmentations together.
    Args:
        transforms (List[Transform]): list of transforms to compose.
    Example:
        >>> transforms.Compose([
        >>>     transforms.CenterCrop(10),
        >>>     transforms.ToTensor(),
        >>> ])
    """

    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        for t in self.transforms:
            img_pre, img_next, boxes_pre, boxes_next, labels = \
                t(img_pre, img_next, boxes_pre, boxes_next, labels)
        return img_pre, img_next, boxes_pre, boxes_next, labels


class ConvertFromInts(object):
    """Transfer the uint8 to float32
    """
    def __call__(self, img_pre, img_next=None,
                 boxes_pre=None, boxes_next=None, labels=None):
        if img_next is not None:
            return img_pre.astype(np.float32), img_next.astype(np.float32), \
                   boxes_pre.astype(np.float32), boxes_next.astype(np.float32), labels
        else:
            return img_pre.astype(np.float32), img_next, \
                   boxes_pre.astype(np.float32), boxes_next, labels

class MoveBoxes(object):
    """Randomly move the centers
    """
    def __init__(self, offset_low=0.0, offset_high=0.2):
        self.offset_low = max(offset_low, 0)
        self.offset_high = max(offset_low, offset_high)
        self.range = self.offset_high - self.offset_low

    def __call__(self, img_pre, img_next=None,
                 boxes_pre=None, boxes_next=None, labels=None):
        def move(img, boxes):
            height, width, channels = img.shape
            center = (boxes[:, :2] + boxes[:, 2:]) / 2.0
            box_width = boxes[:, 2] - boxes[:, 0]
            box_height = boxes[:, 3] - boxes[:, 1]
            t_width = (boxes[:, 2] - boxes[:, 0]) *\
                      (self.range*random.random(boxes.shape[0]) + self.offset_low)
            t_height = (boxes[:, 3] - boxes[:, 1]) *\
                       (self.range*random.random(boxes.shape[0]) + self.offset_low)
            center[:, 0] += t_width * random.choice((-1,1))
            center[:, 1] += t_height * random.choice((-1,1))
            boxes[:, 0] = np.clip(center[:, 0] - box_width / 2.0, 0, width - 1)
            boxes[:, 2] = np.clip(center[:, 0] + box_width / 2.0, 0, width - 1)
            boxes[:, 1] = np.clip(center[:, 1] - box_height / 2.0, 0, height - 1)
            boxes[:, 3] = np.clip(center[:, 1] + box_height / 2.0, 0, height - 1)

        move(img_pre, boxes_pre)
        if boxes_next is not None:
            move(img_next, boxes_next)

        return img_pre, img_next, boxes_pre, boxes_next, labels


class SubtractMeans(object):
    """Image pixes - mean_pixes"""
    def __init__(self, mean):
        self.mean = np.array(mean, dtype=np.float32)

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):

        img_pre = img_pre.astype(np.float32)
        img_pre -= self.mean
        if img_next is not None:
            img_next = img_next.astype(np.float32)
            img_next -= self.mean

        return img_pre, img_next, boxes_pre, boxes_next, labels


class ToPercentCoords(object):
    """Normalize boxes' coordinates to range[0,1]
    """
    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        height, width, channels = img_pre.shape
        boxes_pre[:, 0] /= width
        boxes_pre[:, 2] /= width
        boxes_pre[:, 1] /= height
        boxes_pre[:, 3] /= height

        if boxes_next is not None:
            boxes_next[:, 0] /= width
            boxes_next[:, 2] /= width
            boxes_next[:, 1] /= height
            boxes_next[:, 3] /= height

        return img_pre, img_next, boxes_pre, boxes_next, labels


class Resize(object):
    """Resize images"""
    def __init__(self, size):
        self.size = size

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        img_pre = cv2.resize(img_pre, (self.size, self.size))
        if img_next is not None:
            img_next = cv2.resize(img_next, (self.size, self.size))

        return img_pre, img_next, boxes_pre, boxes_next, labels


class RandomSaturation(object):
    """Adjust Saturation[0,255] by multiply a factor of U[lower,higher]"""
    def __init__(self, lower, upper):
        self.lower = lower
        self.upper = upper
        assert self.upper >= self.lower, "contrast upper must be >= lower."
        assert self.lower >= 0, "contrast lower must be non-negative."

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if random.randint(2):
            alpha = random.uniform(self.lower, self.upper)
            img_pre[:, :, 1] = img_pre[:, :, 1] * alpha
            if img_next is not None:
                img_next[:, :, 1] = img_next[:, :, 1] * alpha

        return img_pre, img_next, boxes_pre, boxes_next, labels


class RandomHue(object):
    """Adjust Hue[0,180] by add a factor of U[-delta,delta]"""
    def __init__(self, delta=18.0):
        assert delta >= 0.0 and delta <= 360.0
        self.delta = delta

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if random.randint(2):
            delta = random.uniform(-self.delta, self.delta)
            img_pre[:, :, 0] = img_pre[:, :, 0] + delta
            img_pre[:, :, 0][img_pre[:, :, 0] > 360.0] -= 360.0
            img_pre[:, :, 0][img_pre[:, :, 0] < 0.0] += 360.0
            if img_next is not None:
                img_next[:, :, 0] = img_next[:, :, 0] + delta
                img_next[:, :, 0][img_next[:, :, 0] > 360.0] -= 360.0
                img_next[:, :, 0][img_next[:, :, 0] < 0.0] += 360.0
        return img_pre, img_next, boxes_pre, boxes_next, labels


class RandomLightingNoise(object):
    """Shuffle the Channels randomly"""
    def __init__(self):
        self.perms = ((0, 1, 2), (0, 2, 1),
                      (1, 0, 2), (1, 2, 0),
                      (2, 0, 1), (2, 1, 0))

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if random.randint(2):
            swap = self.perms[random.randint(len(self.perms))]
            shuffle = SwapChannels(swap)  # shuffle channels
            img_pre = shuffle(img_pre)
            if img_next is not None:
                img_next = shuffle(img_next)
        return img_pre, img_next, boxes_pre, boxes_next, labels


class ConvertColor(object):
    """Convert BGR2HSV or HSV2BGR"""
    def __init__(self, current='BGR', transform='HSV'):
        self.transform = transform
        self.current = current

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if self.current == 'BGR' and self.transform == 'HSV':
            img_pre = cv2.cvtColor(img_pre, cv2.COLOR_BGR2HSV)
            if img_next is not None:
                img_next = cv2.cvtColor(img_next, cv2.COLOR_BGR2HSV)
        elif self.current == 'HSV' and self.transform == 'BGR':
            img_pre = cv2.cvtColor(img_pre, cv2.COLOR_HSV2BGR)
            if img_next is not None:
                img_next = cv2.cvtColor(img_next, cv2.COLOR_HSV2BGR)
        else:
            raise NotImplementedError
        return img_pre, img_next, boxes_pre, boxes_next, labels


class RandomContrast(object):
    """Adjust Contrast[0,255] by multiply a factor of U[lower,higher]"""
    def __init__(self, lower, upper):
        self.lower = lower
        self.upper = upper
        assert self.upper >= self.lower, "contrast upper must be >= lower."
        assert self.lower >= 0, "contrast lower must be non-negative."

    # expects float image
    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if random.randint(2):
            alpha = random.uniform(self.lower, self.upper)
            img_pre = img_pre*alpha
            if img_next is not None:
                img_next = img_next*alpha
        return img_pre, img_next, boxes_pre, boxes_next, labels


class RandomBrightness(object):
    """Adjust Brightness[0,255] by add a factor of U[-delta,delta]"""
    def __init__(self, delta=32):
        assert delta >= 0.0
        assert delta <= 255.0
        self.delta = delta

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if random.randint(2):
            delta = random.uniform(-self.delta, self.delta)
            img_pre = img_pre + delta
            if img_next is not None:
                img_next = img_next + delta
        return img_pre, img_next, boxes_pre, boxes_next, labels


class RandomSampleCrop(object):
    """Crop
    Arguments:
        mode (float tuple): the min and max jaccard overlaps
    """
    def __init__(self, max_object=80):
        self.sample_options = (
            # using entire original input image
            None,
            # sample a patch s.t. MIN jaccard w/ obj in .1,.3,.4,.7,.9
            (0.7, None),
            (0.8, None),
            (0.85, None),
            (0.9, None),
            # randomly sample a patch
            (None, None),
        )
        self.max_object = max_object
    def crop(self, image, boxes, labels, mode, min_iou, max_iou, w, h, left, top, isPre=True):
        """
            cropped image should contain all of the boxes' centers

        """

        current_image = image
        # convert to integer rect x1,y1,x2,y2
        rect = np.array([int(left), int(top), int(left + w), int(top + h)])

        #  IoU (jaccard calculateoverlap) b/t the cropped and gt boxes

        overlap = iou(
            np.c_[boxes[:,:2], boxes[:,2:]-boxes[:,:2]],
            [left, top, w, h])

        # is min and max overlap constraint satisfied? if not try again
        # I think this part makes no sense due to the second judgement is always False
        if overlap.min() < min_iou and max_iou < overlap.max():
            return None

        # cut the crop from the image
        current_image = current_image[rect[1]:rect[3], rect[0]:rect[2], :]

        # keep overlap with gt box IF center in sampled patch
        centers = (boxes[:, :2] + boxes[:, 2:]) / 2.0

        # mask in all gt boxes that above and to the left of centers
        m1 = (rect[0] < centers[:, 0]) * (rect[1] < centers[:, 1])

        # mask in all gt boxes that under and to the right of centers
        m2 = (rect[2] > centers[:, 0]) * (rect[3] > centers[:, 1])

        # mask in that both m1 and m2 are true
        mask = m1 * m2

        # have any valid boxes? try again if not
        if not mask.any():
            return None

        # take only matching gt boxes
        current_boxes = boxes[mask, :].copy()

        # pading the mask
        mask = np.pad(mask,
                      (0, self.max_object - len(mask)),
                      'constant')
        mask = (mask == False)

        # take only matching gt labels
        # Important change: instead assign to zero, we should delete the row
        current_labels = labels
        h, w = labels.shape
        if isPre:
            current_labels = current_labels[np.logical_not(mask), :]
            current_labels = np.pad(current_labels, [[0, h-current_labels.shape[0]], [0, 0]], mode='constant', constant_values=0.0)
        else:
            current_labels = current_labels[:, np.logical_not(mask)]
            current_labels = np.pad(current_labels, [[0, 0], [0, w - current_labels.shape[1]]], mode='constant', constant_values=0.0)

        # should we use the box left and top corner or the crop's
        current_boxes[:, :2] = np.maximum(current_boxes[:, :2],
                                          rect[:2])
        # adjust to crop (by substracting crop's left,top)
        current_boxes[:, :2] -= rect[:2]

        current_boxes[:, 2:] = np.minimum(current_boxes[:, 2:],
                                          rect[2:])
        # adjust to crop (by substracting crop's left,top)
        current_boxes[:, 2:] -= rect[:2]

        return current_image, current_boxes, current_labels


    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        height, width, _ = img_pre.shape
        while True:
            # randomly choose a mode
            mode = random.choice(self.sample_options)
            if mode is None:
                return img_pre, img_next, boxes_pre, boxes_next, labels

            min_iou, max_iou = mode
            if min_iou is None:
                min_iou = float('-inf')
            if max_iou is None:
                max_iou = float('inf')

            # max trails (50)
            for _ in range(50):

                w = random.uniform(0.8 * width, width)
                h = random.uniform(0.8 * height, height)

                # aspect ratio constraint b/t .5 & 2
                if h / w < 0.5 or h / w > 2:
                    continue

                left = random.uniform(width - w)
                top = random.uniform(height - h)

                res_pre = self.crop(img_pre, boxes_pre, labels, mode, min_iou, max_iou, w, h, left, top, isPre=True)
                if res_pre is None:
                    continue
                if img_next is not None:
                    res_next = self.crop(img_next, boxes_next, res_pre[2], mode, min_iou, max_iou, w, h, left, top, isPre=False)
                    if res_next is None:
                        continue
                    else:
                        return res_pre[0], res_next[0], res_pre[1], res_next[1], res_next[2]
                else:
                    return res_pre[0], img_next, res_pre[1], boxes_next, labels


class Expand(object):
    def __init__(self, mean, max_expand):
        self.mean = mean
        self.max_expand = max_expand

    def expand(self, image, height, width, depth, ratio, left, top):
        expand_image = np.zeros(
            (int(height * ratio), int(width * ratio), depth),
            dtype=image.dtype)
        expand_image[:, :, :] = self.mean
        expand_image[int(top):int(top + height), int(left):int(left + width)] = image
        return expand_image

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if random.randint(2):
            return img_pre, img_next, boxes_pre, boxes_next, labels

        height, width, depth = img_pre.shape
        ratio = random.uniform(1, self.max_expand) # new: adjust the max_expand to 2.0 (orgin is 4.0)
        left = random.uniform(0, width * ratio - width)
        top = random.uniform(0, height * ratio - height)

        img_pre = self.expand(img_pre, height, width, depth, ratio, left, top)
        boxes_pre = boxes_pre.copy()
        boxes_pre[:, :2] += (int(left), int(top))
        boxes_pre[:, 2:] += (int(left), int(top))

        if img_next is not None:
            img_next = self.expand(img_next, height, width, depth, ratio, left, top)
            boxes_next = boxes_next.copy()
            boxes_next[:, :2] += (int(left), int(top))
            boxes_next[:, 2:] += (int(left), int(top))

        return img_pre, img_next, boxes_pre, boxes_next, labels


class RandomMirror(object):
    def mirror(self, image, boxes):
        _, width, _ = image.shape
        image = np.array(image[:, ::-1])
        boxes = boxes.copy()
        boxes[:, 0] = width - boxes[:, 0]
        boxes[:, 2] = width - boxes[:, 2]
        return image, boxes

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        if random.randint(2):
            res_pre = self.mirror(img_pre, boxes_pre)
            img_pre = res_pre[0]
            boxes_pre = res_pre[1]

            if img_next is not None:
                res_next = self.mirror(img_next, boxes_next)
                img_next = res_next[0]
                boxes_next = res_next[1]

        return img_pre, img_next, boxes_pre, boxes_next, labels


class SwapChannels(object):
    """Transforms a tensorized image by swapping the channels in the order
     specified in the swap tuple.
    Args:
        swaps (int triple): final order of channels
            eg: (2, 1, 0)
    """

    def __init__(self, swaps):
        self.swaps = swaps

    def __call__(self, image):
        """
        Args:
            image (Tensor): image tensor to be transformed
        Return:
            a tensor with channels swapped according to swap
        """
        # if torch.is_tensor(image):
        #     image = image.data.cpu().numpy()
        # else:
        #     image = np.array(image)
        image = image[:, :, self.swaps]
        return image


class PhotometricDistort(object):
    def __init__(self, lower_contrast, upper_constrast, lower_saturation, upper_saturation):
        self.pd = [
            RandomContrast(lower_contrast, upper_constrast),
            ConvertColor(transform='HSV'),
            RandomSaturation(lower_saturation, upper_saturation),
            RandomHue(),
            ConvertColor(current='HSV', transform='BGR'),
            RandomContrast(lower_contrast, upper_constrast)
        ]
        self.rand_brightness = RandomBrightness()
        self.rand_light_noise = RandomLightingNoise()

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        im_pre = img_pre.copy()
        im_next = img_next.copy()
        im_pre, im_next, boxes_pre, boxes_next, labels = \
            self.rand_brightness(im_pre, im_next, boxes_pre, boxes_next, labels)
        if random.randint(2):
            distort = Compose(self.pd[:-1])
        else:
            distort = Compose(self.pd[1:])

        im_pre, im_next, boxes_pre, boxes_next, labels = distort(im_pre, im_next, boxes_pre, boxes_next, labels)

        return self.rand_light_noise(im_pre, im_next, boxes_pre, boxes_next, labels)


class ResizeShuffleBoxes(object):
    """Transfer the NaxNb labes to (Nm+1)x(Nm+1) lables

    """
    def __init__(self, max_object):
        self.max_object = max_object

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):

        resize_f = lambda boxes: \
            (boxes.shape[0],
             np.vstack((
                 boxes,
                 np.full(
                     (self.max_object - len(boxes),
                      boxes.shape[1]),
                     np.inf
                 ))))

        size_pre, boxes_pre = resize_f(boxes_pre)
        indexes_pre = np.arange(self.max_object)
        np.random.shuffle(indexes_pre)
        boxes_pre = boxes_pre[indexes_pre, :]
        mask_pre = indexes_pre < size_pre

        mask_next = None

        if img_next is not None:
            size_next, boxes_next = resize_f(boxes_next)
            indexes_next = np.arange(self.max_object)
            np.random.shuffle(indexes_next)
            boxes_next = boxes_next[indexes_next, :]
            mask_next = indexes_next < size_next

            labels = labels[indexes_pre, :]
            labels = labels[:, indexes_next]

            # add false object label
            false_object_pre = (labels.sum(1) == 0).astype(float)       # should consider unmatched object
            false_object_pre[np.logical_not(mask_pre)] = 0.0

            false_object_next = (labels.sum(0) == 0).astype(float)  # should consider unmatched object
            false_object_next[np.logical_not(mask_next)] = 0.0

            false_object_pre = np.expand_dims(false_object_pre, axis=1)
            labels = np.concatenate((labels, false_object_pre), axis=1) #Nmx(Nm+1)

            false_object_next = np.append(false_object_next, [0])
            false_object_next = np.expand_dims(false_object_next, axis=0)
            labels = np.concatenate((labels, false_object_next), axis=0)  #(Nm+1)x(Nm+1)
            mask_next = np.append(mask_next, [True])

        mask_pre = np.append(mask_pre, [True])


        return img_pre, img_next, \
               [boxes_pre, mask_pre], \
               [boxes_next, mask_next], \
               labels


class FormatBoxes(object):
    ''' center -> [-1,1]
    note: format the label in order to input into the selector net.
    '''
    def __call__(self,img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):

        '''
        boxes_pre: [N, 4]
        '''
        # convert the center to [-1, 1]
        # (x1,y1) + (x2, y2) - 1=2xcenter ->[-1,1]
        # Nx1x1x2
        f = lambda boxes: np.expand_dims(
            np.expand_dims(
                (boxes[:, :2] + boxes[:, 2:]) - 1,
                axis=1
            ),
            axis=1
        )

        # remove inf

        if img_next is not None:
            boxes_pre[0] = f(boxes_pre[0])
            boxes_pre[0][boxes_pre[0] == np.inf] = 1.5
            boxes_next[0] = f(boxes_next[0])
            boxes_next[0][boxes_next[0] == np.inf] = 1.5
        else:
            boxes_pre = f(boxes_pre)

        return img_pre, img_next, boxes_pre, boxes_next, labels


class ToTensor(object):
    """Opencv image(HWC) -> Tensor(CHW)
    """
    def __call__(self,img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):

        img_pre = torch.from_numpy(img_pre.astype(np.float32)).permute(2, 0, 1)

        if img_next is not None:
            boxes_pre[0] = torch.from_numpy(boxes_pre[0].astype(np.float32))
            boxes_pre[1] = torch.from_numpy(boxes_pre[1].astype(np.uint8))
            img_next = torch.from_numpy(img_next.astype(np.float32)).permute(2, 0, 1)
            boxes_next[0] = torch.from_numpy(boxes_next[0].astype(np.float32))
            boxes_next[1] = torch.from_numpy(boxes_next[1].astype(np.uint8))

            labels = torch.from_numpy(labels).unsqueeze(0)
        else:
            boxes_pre = torch.from_numpy(boxes_pre.astype(np.float32))

        return img_pre, img_next, boxes_pre, boxes_next, labels


class DANAugmentation(object):
    def __init__(self, cfg, type='train'):
        aug = cfg['augmentation']
        data = cfg['datasets']
        self.mean = aug['mean_pixel']
        self.size = data['image_size']
        self.max_object = data['max_object']
        self.max_expand = aug['max_expand']
        if type == 'train':
            self.augment = Compose([
                ConvertFromInts(),
                MoveBoxes(aug['lower_offset'], aug['upper_offset']),
                PhotometricDistort(aug['lower_contrast'], aug['upper_constrast'],
                                   aug['lower_saturation'], aug['upper_saturation']),
                Expand(self.mean, self.max_expand),
                RandomSampleCrop(self.max_object),
                RandomMirror(),
                ToPercentCoords(),
                Resize(self.size),
                SubtractMeans(self.mean),
                ResizeShuffleBoxes(self.max_object),
                FormatBoxes(),
                ToTensor()
            ])
        elif type == 'val' or type == 'valid':
            self.augment = Compose([
                ConvertFromInts(),
                ToPercentCoords(),
                Resize(self.size),
                SubtractMeans(self.mean),
                ResizeShuffleBoxes(self.max_object),
                FormatBoxes(),
                ToTensor()
            ])
        else:
            self.augment = Compose([
                ConvertFromInts(),
                ToPercentCoords(),
                Resize(self.size),
                SubtractMeans(self.mean),
                FormatBoxes(),
                ToTensor()
            ])

    def __call__(self, img_pre, img_next=None, boxes_pre=None, boxes_next=None, labels=None):
        return self.augment(img_pre, img_next, boxes_pre, boxes_next, labels)


def collate_fn(batch):
    img_pre = []
    img_next = []
    boxes_pre = []
    boxes_next = []
    labels = []
    masks_pre = []
    masks_next = []
    for sample in batch:
        img_pre.append(sample[0])
        masks_pre.append(sample[2][1].bool())
        boxes_pre.append(sample[2][0].float())

        if sample[1] is not None:
            img_next.append(sample[1])
            boxes_next.append(sample[3][0].float())
            masks_next.append(sample[3][1].bool())
            labels.append(sample[4].float())

    if len(labels) > 0:
        return torch.stack(img_pre, 0), torch.stack(img_next, 0), \
               torch.stack(boxes_pre, 0), torch.stack(boxes_next, 0), \
               torch.stack(labels, 0), \
               torch.stack(masks_pre, 0).unsqueeze(1), \
               torch.stack(masks_next, 0).unsqueeze(1)
    else:
        return torch.stack(img_pre, 0), torch.stack(boxes_pre, 0),\
               torch.stack(masks_pre, 0).unsqueeze(1)



