"""AI Translater - PDF OCR翻译工具

从扫描PDF中提取文字并翻译成中文，生成双语对照PDF

支持分步执行：
- extract: PDF转图片
- ocr: 图片OCR识别
- translate: 翻译OCR结果
- generate: 生成双语PDF
- all: 完整流程
"""

from .main import OutputFormat
from .ocr_engine import OCREngine
from .pdf_extractor import PDFExtractor
from .pdf_generator import BilingualContent, PDFGenerator
from .translator import Translator

__version__ = "0.1.0"

__all__ = [
    "PDFExtractor",
    "OCREngine", 
    "Translator",
    "PDFGenerator",
    "BilingualContent",
    "OutputFormat",
]
