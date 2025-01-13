Face Mask Detection with YOLOv5
This project uses YOLOv5 for real-time face mask detection. It classifies individuals into three categories:

With Mask
Without Mask
Mask Worn Incorrectly
It demonstrates:

Training YOLOv5 on a custom dataset.
Real-time mask detection using webcam or uploaded videos.
Exporting the model to ONNX, CoreML, and TFLite formats for deployment.
Table of Contents
Setup
Usage
Results
Model Export
Contributing
Setup
Clone the repository and install dependencies:
git clone https://github.com/yasi76/computer-vision.git
cd computer-vision
Usage
Train the Model: Follow the Colab notebook to train YOLOv5 on a custom dataset.
Real-Time Detection: Use your webcam to detect face masks in real-time.
Video Processing: Upload and process a video to detect masks frame by frame.
Example for video processing:
uploaded = files.upload()
video_path = list(uploaded.keys())[0]
cap = cv2.VideoCapture(video_path)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    results = model(frame)
    annotated_frame = results.render()[0]
    out.write(annotated_frame)

cap.release()
out.release()
files.download('output.mp4')
Results
The model detects faces and their mask status in real-time or videos. Results are displayed with annotations on the detected faces.

Model Export
Export the YOLOv5 model to different formats for deployment:
!python /content/yolov5/export.py --weights /content/yolov5/runs/train/exp/weights/best.pt --img 320 --include onnx coreml tflite
License
This project is licensed under the MIT License.

