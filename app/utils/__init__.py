# app/utils/__init__.py (обновленный)
"""
Инициализация вспомогательных утилит
Объединение всех утилит в одном месте
"""
from .contour_metrics import *
from .image_processing import *
from .themes import *

__all__ = [
    'calculate_iou', 'calculate_chamfer_distance', 'calculate_hausdorff_distance',
    'calculate_contour_metrics', 'calculate_comprehensive_contour_score',
    'process_coco_annotations', 'parse_coco_for_image',
    'load_theme', 'apply_theme_to_response'
]

# Фильтр для Jinja2 будет добавлен в app/__init__.py после создания приложения