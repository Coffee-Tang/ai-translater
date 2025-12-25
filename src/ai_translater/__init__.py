"""AI Translater - PDF OCR翻译工具

从扫描PDF中提取文字并翻译成中文，生成双语对照PDF
"""

from .main import OutputFormat, PDFTranslator
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
    "PDFTranslator",
    "OutputFormat",
]

