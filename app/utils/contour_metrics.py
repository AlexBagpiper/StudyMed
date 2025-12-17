# app/utils/contour_metrics.py
"""
Утилиты для оценки контуров приложения медицинского тестирования
Содержит функции для вычисления различных метрик совпадения контуров
"""
import cv2
import numpy as np
from app.models.annotation import ImageAnnotation
from app.utils.image_processing import process_coco_annotations, process_yolo_annotations
from config import Config
import math
import os

def calculate_iou(contour1, contour2):
    """
    Вычисление Intersection over Union между двумя контурами

    Args:
        contour1 (list): Первый контур в формате [(x1,y1), (x2,y2), ...]
        contour2 (list): Второй контур в формате [(x1,y1), (x2,y2), ...]

    Returns:
        float: Значение IoU (0.0 - 1.0)
    """
    # Создание бинарных масок
    all_points = contour1 + contour2
    max_x = max([point[0] for point in all_points])
    max_y = max([point[1] for point in all_points])

    # Использование подходящего размера для маски с отступом
    mask_size = (max(int(max_x) + 50, 512), max(int(max_y) + 50, 512))
    mask1 = np.zeros(mask_size, dtype=np.uint8)
    mask2 = np.zeros(mask_size, dtype=np.uint8)

    # Рисование контуров на масках
    contour1_np = np.array(contour1, dtype=np.int32)
    contour2_np = np.array(contour2, dtype=np.int32)

    cv2.fillPoly(mask1, [contour1_np], 255)
    cv2.fillPoly(mask2, [contour2_np], 255)

    # Вычисление пересечения и объединения
    intersection = cv2.bitwise_and(mask1, mask2)
    union = cv2.bitwise_or(mask1, mask2)

    intersection_area = cv2.countNonZero(intersection)
    union_area = cv2.countNonZero(union)

    if union_area == 0:
        return 0.0

    return intersection_area / union_area

def calculate_chamfer_distance(contour1, contour2):
    """
    Вычисление расстояния Чамфера между двумя контурами

    Args:
        contour1 (list): Первый контур в формате [(x1,y1), (x2,y2), ...]
        contour2 (list): Второй контур в формате [(x1,y1), (x2,y2), ...]

    Returns:
        float: Значение расстояния Чамфера
    """
    # Преобразование в массивы numpy
    c1 = np.array(contour1, dtype=np.float32)
    c2 = np.array(contour2, dtype=np.float32)

    # Вычисление расстояний от каждой точки контура1 до ближайшей точки контура2
    dists_1_to_2 = []
    for p1 in c1:
        min_dist = float('inf')
        for p2 in c2:
            dist = np.linalg.norm(p1 - p2)
            if dist < min_dist:
                min_dist = dist
        dists_1_to_2.append(min_dist)

    # Вычисление расстояний от каждой точки контура2 до ближайшей точки контура1
    dists_2_to_1 = []
    for p2 in c2:
        min_dist = float('inf')
        for p1 in c1:
            dist = np.linalg.norm(p2 - p1)
            if dist < min_dist:
                min_dist = dist
        dists_2_to_1.append(min_dist)

    # Расстояние Чамфера - сумма обоих направлений
    chamfer_dist = np.mean(dists_1_to_2) + np.mean(dists_2_to_1)

    return chamfer_dist

def calculate_hausdorff_distance(contour1, contour2):
    """
    Вычисление расстояния Хаусдорфа между двумя контурами

    Args:
        contour1 (list): Первый контур в формате [(x1,y1), (x2,y2), ...]
        contour2 (list): Второй контур в формате [(x1,y1), (x2,y2), ...]

    Returns:
        float: Значение расстояния Хаусдорфа
    """
    # Преобразование в массивы numpy
    c1 = np.array(contour1, dtype=np.float32)
    c2 = np.array(contour2, dtype=np.float32)

    # Вычисление направленного расстояния Хаусдорфа от c1 к c2
    hausdorff_1_to_2 = 0
    for p1 in c1:
        min_dist = float('inf')
        for p2 in c2:
            dist = np.linalg.norm(p1 - p2)
            if dist < min_dist:
                min_dist = dist
        if min_dist > hausdorff_1_to_2:
            hausdorff_1_to_2 = min_dist

    # Вычисление направленного расстояния Хаусдорфа от c2 к c1
    hausdorff_2_to_1 = 0
    for p2 in c2:
        min_dist = float('inf')
        for p1 in c1:
            dist = np.linalg.norm(p2 - p1)
            if dist < min_dist:
                min_dist = dist
        if min_dist > hausdorff_2_to_1:
            hausdorff_2_to_1 = min_dist

    # Возвращение максимального из двух направленных расстояний
    return max(hausdorff_1_to_2, hausdorff_2_to_1)

def calculate_contour_metrics(contour1, contour2, expected_label=None, user_label=None):
    """
    Вычисление нескольких метрик для сравнения двух контуров с дополнительным контекстом

    Args:
        contour1 (list): Контур пользователя
        contour2 (list): Контур эталона
        expected_label (str): Ожидаемая метка
        user_label (str): Пользовательская метка

    Returns:
        dict: Словарь с вычисленными метриками
    """
    iou = calculate_iou(contour1, contour2)
    chamfer_dist = calculate_chamfer_distance(contour1, contour2)
    hausdorff_dist = calculate_hausdorff_distance(contour1, contour2)

    # Дополнительные метрики
    c1 = np.array(contour1, dtype=np.float32)
    c2 = np.array(contour2, dtype=np.float32)

    # Схожесть площадей
    area1 = cv2.contourArea(c1.astype(np.int32))
    area2 = cv2.contourArea(c2.astype(np.int32))
    area_similarity = min(area1, area2) / max(area1, area2) if max(area1, area2) > 0 else 0

    # Схожесть периметра
    perimeter1 = cv2.arcLength(c1.astype(np.float32), True)  # Замкнутый контур
    perimeter2 = cv2.arcLength(c2.astype(np.float32), True)  # Замкнутый контур
    perimeter_similarity = min(perimeter1, perimeter2) / max(perimeter1, perimeter2) if max(perimeter1, perimeter2) > 0 else 0

    # Совпадение границ (обратное расстояние Чамфера, нормализованное)
    max_possible_distance = max(area1, area2) ** 0.5 if max(area1, area2) > 0 else 1
    boundary_match = max(0, 1 - chamfer_dist / max_possible_distance)

    # Проверка присутствия (если контур примерно в правильном месте)
    # Вычисление центров масс
    M1 = cv2.moments(c1.astype(np.int32))
    M2 = cv2.moments(c2.astype(np.int32))
    if M1['m00'] != 0 and M2['m00'] != 0:
        cx1, cy1 = M1['m10']/M1['m00'], M1['m01']/M1['m00']
        cx2, cy2 = M2['m10']/M2['m00'], M2['m01']/M2['m00']
        center_distance = math.sqrt((cx1-cx2)**2 + (cy1-cy2)**2)
        # Нормализация по среднему размеру контуров
        avg_size = (area1 + area2) / 2 if area1 + area2 > 0 else 1
        normalized_distance = center_distance / (avg_size ** 0.5)
        presence_score = max(0, 1 - normalized_distance / 2)  # Балл от 0 до 1
    else:
        presence_score = 0

    # Совпадение метки с допуском
    label_match = 0.0
    if expected_label and user_label:
        # Проверка совпадения меток (без учета регистра)
        if expected_label.lower() == user_label.lower():
            # Дополнительная проверка: контур должен значительно перекрывать эталон
            if iou >= Config.LABEL_THRESHOLD['overlap_ratio']:
                # Проверка допуска по площади
                area_diff = abs(area1 - area2) / max(area1, area2) if max(area1, area2) > 0 else 0
                if area_diff <= Config.LABEL_THRESHOLD['area_tolerance']:
                    label_match = 1.0
                else:
                    # Частичный балл за правильную метку, но неправильный размер
                    label_match = 0.5
            else:
                # Частичный балл за правильную метку, но плохое перекрытие
                label_match = 0.3
        else:
            # Проверка на похожие метки (можно реализовать более сложное сопоставление)
            label_match = 0.0

    return {
        'iou': iou,
        'chamfer_distance': chamfer_dist,
        'hausdorff_distance': hausdorff_dist,
        'area_similarity': area_similarity,
        'perimeter_similarity': perimeter_similarity,
        'boundary_match': boundary_match,
        'presence_score': presence_score,
        'label_match': label_match,
        'expected_label': expected_label,
        'user_label': user_label,
        'area1': area1,
        'area2': area2
    }

def calculate_comprehensive_contour_score(contour_metrics):
    """
    Вычисление комплексного балла на основе нескольких метрик контуров

    Args:
        contour_metrics (dict): Словарь с метриками контуров

    Returns:
        float: Комплексный балл (0.0 - 1.0)
    """
    weights = Config.CONTOUR_METRICS_WEIGHTS
    score = (
        contour_metrics['iou'] * weights['iou'] +
        contour_metrics['boundary_match'] * weights['boundary_match'] +
        contour_metrics['presence_score'] * weights['presence'] +
        contour_metrics['label_match'] * weights['label_match']
    )
    return min(score, 1.0)  # Обеспечение, что балл не превышает 1.0

def evaluate_graphic_answer_with_metrics(question_id, user_contours):
    """
    Оценка графического ответа студента с детальными метриками

    Args:
        question_id (int): ID вопроса
        user_contours (list): Контуры, нарисованные студентом

    Returns:
        dict: Результаты оценки с метриками
    """
    from app.models.question import Question
    from app import db

    question = Question.query.get(question_id)
    if not question:
        return {'error': 'Вопрос не найден'}

    # Получение ID аннотации из поля correct_answer
    try:
        annotation_id = int(question.correct_answer)
    except ValueError:
        return {'error': 'Неверная ссылка на аннотацию'}

    annotation = ImageAnnotation.query.get(annotation_id)
    if not annotation:
        return {'error': 'Аннотация не найдена'}

    annotation_path = os.path.join(db.session.bind.url.database, 'app', 'static', 'uploads', annotation.annotation_file)

    if annotation.format_type == 'coco':
        correct_data = process_coco_annotations(annotation_path)
    else:  # YOLO
        image_path = os.path.join(db.session.bind.url.database, 'app', 'static', 'uploads', annotation.filename)
        img = cv2.imread(image_path)
        if img is None:
            return {'error': 'Не удалось загрузить изображение'}
        correct_data = process_yolo_annotations(annotation_path, img.shape)

    if not correct_data:
        return {'error': 'Не удалось загрузить правильные ответы'}

    # Сравнение пользовательских контуров с правильными
    scores = []
    detailed_metrics = []
    correct_annotations = correct_data['annotations']

    for user_contour in user_contours:
        best_score = 0
        best_metrics = None

        for correct_ann in correct_annotations:
            # Проверка формата контуров
            if 'points' in user_contour and 'contour' in correct_ann:
                # Использование пользовательской метки если доступна, иначе заглушка
                user_label = user_contour.get('label', 'unknown')

                contour_metrics = calculate_contour_metrics(
                    user_contour['points'],
                    correct_ann['contour'],
                    correct_ann['label'],
                    user_label
                )

                # Вычисление комплексного балла
                comprehensive_score = calculate_comprehensive_contour_score(contour_metrics)

                if comprehensive_score > best_score:
                    best_score = comprehensive_score
                    best_metrics = {
                        'label': correct_ann['label'],
                        'user_label': user_label,
                        'iou': contour_metrics['iou'],
                        'chamfer_distance': contour_metrics['chamfer_distance'],
                        'hausdorff_distance': contour_metrics['hausdorff_distance'],
                        'area_similarity': contour_metrics['area_similarity'],
                        'perimeter_similarity': contour_metrics['perimeter_similarity'],
                        'boundary_match': contour_metrics['boundary_match'],
                        'presence_score': contour_metrics['presence_score'],
                        'label_match': contour_metrics['label_match'],
                        'comprehensive_score': comprehensive_score,
                        'area1': contour_metrics['area1'],
                        'area2': contour_metrics['area2']
                    }

        scores.append(best_score)
        detailed_metrics.append(best_metrics)

    # Вычисление среднего балла
    avg_score = sum(scores) / len(scores) if scores else 0

    return {
        'average_score': avg_score,
        'max_score': 1.0,
        'individual_scores': scores,
        'detailed_metrics': detailed_metrics,
        'total_contours_detected': len(user_contours),
        'correct_contours_found': len([s for s in scores if s >= Config.CONTOUR_THRESHOLD]),
        'comprehensive_score': avg_score,  # Общий балл за вопрос
        'breakdown': {
            'iou_component': avg_score * Config.CONTOUR_METRICS_WEIGHTS['iou'] if scores else 0,
            'boundary_component': avg_score * Config.CONTOUR_METRICS_WEIGHTS['boundary_match'] if scores else 0,
            'presence_component': avg_score * Config.CONTOUR_METRICS_WEIGHTS['presence'] if scores else 0,
            'label_component': avg_score * Config.CONTOUR_METRICS_WEIGHTS['label_match'] if scores else 0
        }
    }