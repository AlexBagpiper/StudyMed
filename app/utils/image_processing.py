# app/utils/image_processing.py (обновленный)
"""
Утилиты для обработки изображений приложения медицинского тестирования
Содержит функции для обработки COCO и YOLO аннотаций
"""
import json
import cv2
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

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

def parse_coco_for_image(coco_file_path, image_filename, unique_id=None, output_dir=None):
    """
    Парсит COCO-файл и извлекает аннотации, категории и информацию об изображении
    для конкретного изображения по имени файла.

    Args:
        coco_file_path (str): Путь к исходному файлу COCO JSON.
        image_filename (str): Имя изображения (например, 'image.jpg'), для которого извлекаются данные.
        unique_id (str): Уникальная приставка к имени файла.
        output_dir (str, optional): Каталог для сохранения нового файла. Если None, сохраняет рядом с исходным.

    Returns:
        tuple: (bool, str)
            - bool: True, если успешно, False в случае ошибки.
            - str: Имя созданного файла (если успех) или сообщение об ошибке.
    """
    try:
        with open(coco_file_path, 'r', encoding='utf-8') as f:
            coco_data = json.load(f)

        # Найти ID изображения по имени
        image_id = None
        for img_info in coco_data.get('images', []):
            if img_info['file_name'] == image_filename:
                image_id = img_info['id']
                break

        if image_id is None:
            logger.error(f"Изображение '{image_filename}' не найдено в COCO-файле '{coco_file_path}'.")
            return False, f"Изображение '{image_filename}' не найдено в файле аннотаций."

        # Собрать данные для нового файла
        new_coco_data = {
            "info": coco_data.get("info", {}),
            "licenses": coco_data.get("licenses", []),
            "categories": [], # Заполним позже
            "images": [],
            "annotations": []
        }

        # Найти изображение
        for img_info in coco_data.get('images', []):
            if img_info['id'] == image_id:
                new_coco_data['images'].append(img_info)
                break

        # Найти аннотации для этого изображения
        annotation_categories = set()
        for ann in coco_data.get('annotations', []):
            if ann['image_id'] == image_id:
                new_coco_data['annotations'].append(ann)
                annotation_categories.add(ann['category_id'])

        # Найти соответствующие категории
        category_map = {cat['id']: cat for cat in coco_data.get('categories', [])}
        for cat_id in sorted(annotation_categories): # Сортировка для предсказуемости
            if cat_id in category_map:
                new_coco_data['categories'].append(category_map[cat_id])

        # Определить имя и путь для нового файла
        if output_dir is None:
            output_dir = os.path.dirname(coco_file_path)
        original_filename = os.path.basename(coco_file_path)
        name_part, ext_part = os.path.splitext(original_filename)
        name_part_img, ext_part_img = os.path.splitext(image_filename)
        if unique_id:
            new_filename = f"{name_part_img}_{unique_id}{ext_part}"
        else:
            new_filename = f"{name_part_img}{ext_part}"
        new_file_path = os.path.join(output_dir, new_filename)

        # Сохранить новый файл
        with open(new_file_path, 'w', encoding='utf-8') as f:
            json.dump(new_coco_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Создан новый COCO-файл для изображения '{image_filename}': {new_file_path}")
        return True, new_filename

    except FileNotFoundError:
        logger.error(f"COCO-файл не найден: {coco_file_path}")
        return False, f"Файл аннотаций не найден: {coco_file_path}"
    except json.JSONDecodeError:
        logger.error(f"Неверный формат JSON в COCO-файле: {coco_file_path}")
        return False, f"Неверный формат JSON в файле аннотаций: {coco_file_path}"
    except KeyError as e:
        logger.error(f"Отсутствует ожидаемое поле в COCO-файле {coco_file_path}: {e}")
        return False, f"Некорректная структура файла аннотаций: {e}"
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при парсинге COCO-файла '{coco_file_path}': {e}")
        return False, f"Ошибка при обработке файла аннотаций: {str(e)}"