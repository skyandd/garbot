#%tensorflow_version 1.x
import os
import cv2
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image as tfimage
import numpy as np
from keras_vggface import utils


base_dir = os.path.dirname(__file__)
prototxt_path = os.path.join(base_dir + 'models/deploy.prototxt')
caffemodel_path = os.path.join(base_dir + 'models/weights.caffemodel')
dir_path = 'photo/'  # Путь до папки, куда будут заливаться фото
dir_faces = 'photo/faces/'  # Путь до папки, где будут хранить вырезанные лицы
dir_faces_recognition = 'photo/faces_recognition/'  # Путь до папки, где будет лежать фоточка с боксами

model = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
file = os.listdir(path = base_dir + dir_path)[1]
print(file)

# Считываем картину
image = cv2.imread(base_dir + dir_path + file)
(h, w) = image.shape[:2]
blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))

model.setInput(blob)
detections = model.forward()

# Рисуем боксы
counter = 0
for i in range(0, detections.shape[2]):
    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
    (startX, startY, endX, endY) = box.astype("int")
    confidence = detections[0, 0, i, 2]

    if confidence > 0.4:
        counter += 1
        diff = ((endY - startY) - (endX - startX))
        cv2.rectangle(image, (startX - diff, startY - diff // 2), (endX + diff, endY + diff // 2), (255, 255, 255), 2)

        org = (startX - diff, startY - diff // 2 - 10)
        cv2.putText(image, 'person' + str(counter), org,
                    cv2.FONT_HERSHEY_COMPLEX, 0.5, (0, 0, 0), 1)

# Записываем картинку в дирректорию
cv2.imwrite(base_dir + dir_faces + file, image)

# Для того чтобы не вырезать лица из картинки с нарисованными боксами, повторим предыдущий пункт
image = cv2.imread(base_dir + dir_path + file)
(h, w) = image.shape[:2]
blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))

model.setInput(blob)
detections = model.forward()

# Вырезаем лица и сохраняем в дирректорию
for i in range(0, detections.shape[2]):
    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
    (startX, startY, endX, endY) = box.astype("int")
    confidence = detections[0, 0, i, 2]

    # Поставим порог 0.4, на всякий пожарный)))
    if confidence > 0.4:
        diff = ((endY - startY) - (endX - startX))
        frame = image[startY - diff // 2:endY + diff // 2, startX - diff:endX + diff]
        cv2.imwrite(base_dir + dir_faces_recognition + 'person_' + str(i) + file, frame)

model_multitask = load_model("models/checkpoint_best.h5")

gender_mapping = {0: 'Male', 1: 'Female'}
race_mapping = dict( list (enumerate (('White', 'Black', 'Asian', 'Indian', 'Others'))))
max_age = 116.0

counter = 0
title_obj = str()
for filename in os.listdir(path= base_dir + dir_faces_recognition):
    counter += 1
    img = tfimage.load_img(base_dir + dir_faces_recognition + filename, target_size=(224, 224))
    x = tfimage.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = utils.preprocess_input(x, version=2)
    predicted_labels = model_multitask.predict(x)
    gender, race, age = int(predicted_labels[0][0] > 0.5), np.argmax(predicted_labels[1][0]), predicted_labels[2][0]
    title_obj + "Person" + str(counter) + f": {gender_mapping[gender]}, {race_mapping[race]}, {int(age[0] * max_age)}." + '\n'
    print(title_obj)