# import json
# import os
# import torch
# from torchsummary import summary
# from io import StringIO
# from contextlib import redirect_stdout
#
# # Directory where model JSON files will be stored
# ARCHITECTURE_JSON_DIR = "static/model_architecture_json/"
#
#
# def extract_trainable_layers(model, model_id):
#     """
#     Extracts trainable layers from a PyTorch model and saves them as a JSON file.
#     - Trainable layers are those where `Param # != 0`
#     - Uses `torchsummary.summary()` to get layer details.
#     """
#     os.makedirs(ARCHITECTURE_JSON_DIR, exist_ok=True)
#
#     # Redirect torchsummary output to a string buffer
#     buffer = StringIO()
#     with redirect_stdout(buffer):
#         summary(model, input_size=(3, 224, 224))  # Assuming an image model with 3x224x224 input
#
#     output = buffer.getvalue()
#     lines = output.split("\n")  # Convert output to lines
#
#     model_params = {
#         "Visualization-Layer-Parameters": {}
#     }
#
#     # Process each line and extract Layer Type, Output Shape, and Param #
#     for line in lines[3:]:  # Skip the header
#         parts = line.split()
#         if len(parts) < 4:  # Ignore invalid lines
#             continue
#
#         layer_name = parts[0]  # First column is Layer Type
#         param_count = parts[-1]  # Last column is Param #
#
#         try:
#             param_count = int(param_count)  # Convert to integer
#         except ValueError:
#             continue  # Skip if it's not a number
#
#         if param_count > 0:  # **Only keep trainable layers**
#             model_params["Visualization-Layer-Parameters"][layer_name] = [param_count, param_count + 5]  # Example range
#
#     # Define JSON file path
#     json_file_path = os.path.join(ARCHITECTURE_JSON_DIR, f"model_{model_id}.json")
#
#     # Save JSON data
#     with open(json_file_path, "w") as json_file:
#         json.dump(model_params, json_file, indent=4)
#
#     print(f"Model architecture saved at: {json_file_path}")
#
#
# if __name__ == "__main__":
#     # Example: Use a pre-trained ResNet model for testing
#     model = torch.hub.load('pytorch/vision:v0.10.0', 'resnet50', pretrained=True)
#     extract_trainable_layers(model, model_id="resnet50")

import json
import os
import torch
from torchsummary import summary
from io import StringIO
from contextlib import redirect_stdout

ARCHITECTURE_JSON_DIR = "static/model_architecture_json/"

import json
import os
import torch
from torchsummary import summary
from io import StringIO
from contextlib import redirect_stdout

ARCHITECTURE_JSON_DIR = "static/model_architecture_json/"


def extract_model_parameters(model, model_id):
    """
    Extracts model layer details (Layer Name, Output Shape, Param #) and saves as JSON.
    """
    os.makedirs(ARCHITECTURE_JSON_DIR, exist_ok=True)

    model_params = {"layers": []}

    buffer = StringIO()
    with redirect_stdout(buffer):
        summary(model, input_size=(3, 224, 224))

    output = buffer.getvalue()
    lines = output.split("\n")

    for line in lines[3:]:
        parts = line.split()
        if len(parts) < 4:
            continue

        print(parts)
        layer_name = parts[0]
        output_shape = parts[1]
        param_count = parts[-1]

        try:
            param_count = int(param_count)
        except ValueError:
            continue

        model_params["layers"].append({
            "layer_name": layer_name,
            "output_shape": output_shape,
            "param_count": param_count
        })


    json_file_path = os.path.join(ARCHITECTURE_JSON_DIR, f"model_{model_id}.json")

    with open(json_file_path, "w") as json_file:
        json.dump(model_params, json_file, indent=4)

    print(f"✅ Model architecture saved at: {json_file_path}")
    print(json.dumps(model_params, indent=4))


if __name__ == "__main__":
    model = torch.hub.load('pytorch/vision:v0.10.0', 'resnet50', pretrained=True)
    extract_model_parameters(model, model_id="1226")
