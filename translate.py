import cv2
import pytesseract
import time

time_start = time.time()
# 👇 Hardcode your image path here
IMAGE_PATH = "cropped_images/top_left_corner.png"
img = cv2.imread(IMAGE_PATH)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
text = pytesseract.image_to_string(gray, lang="eng")
print(text)
time_end = time.time()
print(f"Time taken: {time_end - time_start:.2f} seconds")