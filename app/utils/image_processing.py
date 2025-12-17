# app/utils/image_processing.py
"""
Утилиты для обработки изображений приложения медицинского тестирования
Содержит функции для обработки COCO и YOLO аннотаций
"""
import json
import cv2
import numpy as np

def process_coco_annotations(annotation_file):
    """
    Обработка файла аннотаций в формате COCO

    Args:
        annotation_file (str): Путь к файлу аннотаций COCO

    Returns:
        dict: Словарь с обработанными аннотациями и метками
    """
    try:
        with open(annotation_file, 'r') as f:
            coco_data = json.load(f)

        annotations = []
        categories = {cat['id']: cat['name'] for cat in coco_data.get('categories', [])}

        for ann in coco_data.get('annotations', []):
            category_name = categories.get(ann['category_id'], f'object_{ann["category_id"]}')
            segmentation = ann.get('segmentation', [])

            if segmentation and isinstance(segmentation[0], list):
                # Преобразование сегментации в контуры
                for seg in segmentation:
                    if len(seg) >= 6:  # Требуется не менее 3 точек для полигона
                        contour = np.array(seg).reshape(-1, 2)
                        annotations.append({
                            'label': category_name,
                            'contour': contour.astype(float).tolist(),
                            'bbox': ann.get('bbox')
                        })

        return {
            'labels': list(categories.values()),
            'annotations': annotations
        }
    except Exception as e:
        print(f"Ошибка обработки аннотаций COCO: {e}")
        return None

def process_yolo_annotations(annotation_file, image_shape):
    """
    Обработка файла аннотаций в формате YOLO

    Args:
        annotation_file (str): Путь к файлу аннотаций YOLO
        image_shape (tuple): Форма изображения (высота, ширина, каналы)

    Returns:
        dict: Словарь с обработанными аннотациями и метками
    """
    try:
        height, width = image_shape[:2]
        annotations = []

        with open(annotation_file, 'r') as f:
            lines = f.readlines()

        # Упрощенный подход - в реальной реализации
        # потребуется правильное сопоставление классов
        class_names = [f"class_{i}" for i in range(100)]  # Заглушка

        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 5:
                class_id = int(parts[0])
                x_center = float(parts[1]) * width
                y_center = float(parts[2]) * height
                bbox_width = float(parts[3]) * width
                bbox_height = float(parts[4]) * height

                # Создание ограничивающего прямоугольника как контура
                x1 = int(x_center - bbox_width / 2)
                y1 = int(y_center - bbox_height / 2)
                x2 = int(x_center + bbox_width / 2)
                y2 = int(y_center + bbox_height / 2)

                contour = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32)

                annotations.append({
                    'label': class_names[class_id] if class_id < len(class_names) else f'class_{class_id}',
                    'contour': contour.astype(float).tolist(),
                    'bbox': [x1, y1, bbox_width, bbox_height]
                })

        return {
            'labels': class_names,
            'annotations': annotations
        }
    except Exception as e:
        print(f"Ошибка обработки аннотаций YOLO: {e}")
        return None