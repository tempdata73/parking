import torch
import numpy as np

from torchvision import transforms
from torchvision.models.detection import fasterrcnn_resnet50_fpn


def load_inference_resnet50(gpu_device_name=None):
    # instantiate model either on cpu or gpu
    device_name = "cpu" if gpu_device_name is None else gpu_device_name
    device = torch.device(device_name)

    # load pretrained model
    model = fasterrcnn_resnet50_fpn(pretrained=True)

    # set model to inference mode
    model = fasterrcnn_resnet50_fpn(pretrained=True)
    for param in model.parameters():
        param.requires_grad = False
    with torch.no_grad():
        model.eval()

    return model.to(device)


def preprocess_input(image):
    transformer = transforms.ToTensor()
    tensor_image = transformer(image)
    batch_input = tensor_image.unsqueeze(0)
    return batch_input


def filter_objects(model_output, coco_cat_names, threshold):
    bboxes = model_output["boxes"].numpy().astype("int")
    labels = model_output["labels"].numpy()
    scores = model_output["scores"].numpy()

    idxs = np.where(np.isin(labels, coco_cat_names) & (scores >= threshold))
    filtered_bboxes = bboxes[idxs]
    return filtered_bboxes


def detect_objects(model, image, coco_cat_names, threshold=0):
    image_input = preprocess_input(image)
    output = model(image_input)[0]
    bboxes = filter_objects(output, coco_cat_names, threshold)
    return bboxes
