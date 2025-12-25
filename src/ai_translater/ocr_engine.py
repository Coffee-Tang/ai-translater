"""OCR引擎模块 - 使用PaddleOCR进行文字识别"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image


@dataclass
class TextBlock:
    """文字块数据结构"""
    text: str  # 识别的文字
    confidence: float  # 置信度
    bbox: List[List[float]]  # 边界框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    
    @property
    def x(self) -> float:
        """获取左上角x坐标"""
        return min(p[0] for p in self.bbox)
    
    @property
    def y(self) -> float:
        """获取左上角y坐标"""
        return min(p[1] for p in self.bbox)
    
    @property
    def width(self) -> float:
        """获取宽度"""
        return max(p[0] for p in self.bbox) - self.x
    
    @property
    def height(self) -> float:
        """获取高度"""
        return max(p[1] for p in self.bbox) - self.y


@dataclass
class PageOCRResult:
    """页面OCR结果"""
    page_num: int  # 页码
    text_blocks: List[TextBlock]  # 文字块列表
    full_text: str  # 完整文本
    
    @property
    def has_text(self) -> bool:
        """是否包含文字"""
        return len(self.text_blocks) > 0


class OCREngine:
    """OCR引擎 - 使用PaddleOCR进行文字识别 (PaddleOCR 3.x版本)"""

    def __init__(
        self,
        lang: str = "en",
    ):
        """初始化OCR引擎
        
        Args:
            lang: 识别语言，'en'英文, 'ch'中文等
        """
        self.lang = lang
        # PaddleOCR 3.x 初始化方式
        self.ocr = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
        page_num: int = 0,
    ) -> PageOCRResult:
        """识别图片中的文字
        
        Args:
            image: 图片路径、PIL Image对象或numpy数组
            page_num: 页码标识
            
        Returns:
            PageOCRResult对象
        """
        # 转换图片格式
        if isinstance(image, (str, Path)):
            img_input = str(image)
        elif isinstance(image, Image.Image):
            img_input = np.array(image)
        else:
            img_input = image

        # 执行OCR识别 (PaddleOCR 3.x API)
        result = self.ocr.predict(img_input)
        
        # 解析结果 (PaddleOCR 3.x 返回格式)
        text_blocks: List[TextBlock] = []
        
        for res in result:
            # 获取OCR结果
            ocr_result = res.get("ocr_result", []) if isinstance(res, dict) else []
            
            for item in ocr_result:
                bbox = item.get("bbox", [])
                text = item.get("text", "")
                score = item.get("score", 0.0)
                
                if text and bbox:
                    text_blocks.append(TextBlock(
                        text=text,
                        confidence=score,
                        bbox=bbox,
                    ))

        # 按位置排序：先按y坐标（行），再按x坐标（列）
        text_blocks.sort(key=lambda b: (b.y, b.x))
        
        # 生成完整文本
        full_text = self._merge_text_blocks(text_blocks)

        return PageOCRResult(
            page_num=page_num,
            text_blocks=text_blocks,
            full_text=full_text,
        )

    def recognize_batch(
        self,
        images: List[Union[str, Path, Image.Image, np.ndarray]],
    ) -> List[PageOCRResult]:
        """批量识别多张图片
        
        Args:
            images: 图片列表
            
        Returns:
            PageOCRResult列表
        """
        results = []
        for i, img in enumerate(images):
            result = self.recognize(img, page_num=i)
            results.append(result)
        return results

    def _merge_text_blocks(
        self,
        text_blocks: List[TextBlock],
        line_threshold: float = 20.0,
    ) -> str:
        """合并文字块为完整文本
        
        Args:
            text_blocks: 文字块列表
            line_threshold: 判断是否同一行的y坐标阈值
            
        Returns:
            合并后的文本
        """
        if not text_blocks:
            return ""

        lines: List[List[TextBlock]] = []
        current_line: List[TextBlock] = []
        last_y = None

        for block in text_blocks:
            if last_y is None or abs(block.y - last_y) < line_threshold:
                current_line.append(block)
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [block]
            last_y = block.y

        if current_line:
            lines.append(current_line)

        # 每行内按x坐标排序，然后合并
        text_lines = []
        for line in lines:
            line.sort(key=lambda b: b.x)
            line_text = " ".join(b.text for b in line)
            text_lines.append(line_text)

        return "\n".join(text_lines)

    def extract_text_only(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
    ) -> str:
        """仅提取文本，不返回位置信息
        
        Args:
            image: 图片
            
        Returns:
            识别的文本
        """
        result = self.recognize(image)
        return result.full_text
