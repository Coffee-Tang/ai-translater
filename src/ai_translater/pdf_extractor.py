"""PDF提取模块 - 将PDF页面转换为图片"""

import os
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF
from PIL import Image


class PDFExtractor:
    """PDF提取器 - 将PDF每页转换为图片用于OCR处理"""

    def __init__(self, dpi: int = 300):
        """初始化PDF提取器
        
        Args:
            dpi: 图片分辨率，默认300 DPI，更高的DPI有助于OCR识别
        """
        self.dpi = dpi
        self.zoom = dpi / 72  # PDF默认72 DPI

    def extract_pages(
        self,
        pdf_path: str | Path,
        output_dir: Optional[str | Path] = None,
        page_range: Optional[tuple[int, int]] = None,
    ) -> List[Image.Image]:
        """从PDF中提取页面为图片
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 可选，保存图片的目录
            page_range: 可选，页面范围 (start, end)，从0开始
            
        Returns:
            PIL Image对象列表
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        images: List[Image.Image] = []
        
        # 打开PDF文档
        doc = fitz.open(str(pdf_path))
        
        try:
            # 确定页面范围
            start_page = 0
            end_page = len(doc)
            
            if page_range:
                start_page = max(0, page_range[0])
                end_page = min(len(doc), page_range[1])

            # 创建输出目录
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

            # 转换每一页
            for page_num in range(start_page, end_page):
                page = doc[page_num]
                
                # 创建变换矩阵以提高分辨率
                mat = fitz.Matrix(self.zoom, self.zoom)
                
                # 渲染页面为图片
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                # 转换为PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)

                # 如果指定了输出目录，保存图片
                if output_dir:
                    img_path = output_dir / f"page_{page_num + 1:04d}.png"
                    img.save(str(img_path), "PNG")

        finally:
            doc.close()

        return images

    def get_page_count(self, pdf_path: str | Path) -> int:
        """获取PDF页数
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDF页数
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count

    def extract_page(
        self, 
        pdf_path: str | Path, 
        page_num: int
    ) -> Image.Image:
        """提取单页PDF为图片
        
        Args:
            pdf_path: PDF文件路径
            page_num: 页码，从0开始
            
        Returns:
            PIL Image对象
        """
        images = self.extract_pages(pdf_path, page_range=(page_num, page_num + 1))
        if not images:
            raise ValueError(f"无法提取页面 {page_num}")
        return images[0]

