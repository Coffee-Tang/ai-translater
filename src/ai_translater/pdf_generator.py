"""PDF生成模块 - 生成双语对照PDF"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


@dataclass
class BilingualContent:
    """双语内容"""
    original: str  # 原文
    translated: str  # 译文
    page_num: int  # 原始页码


class PDFGenerator:
    """PDF生成器 - 生成双语对照PDF"""

    # 常用中文字体路径
    CHINESE_FONT_PATHS = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ]

    def __init__(
        self,
        page_size: Tuple[float, float] = A4,
        margin: float = 2.0 * cm,
        font_size: int = 10,
        line_spacing: float = 1.5,
    ):
        """初始化PDF生成器
        
        Args:
            page_size: 页面大小，默认A4
            margin: 页边距，默认2cm
            font_size: 字体大小
            line_spacing: 行间距
        """
        self.page_size = page_size
        self.margin = margin
        self.font_size = font_size
        self.line_spacing = line_spacing
        
        # 注册中文字体
        self._register_chinese_font()
        
        # 创建样式
        self._create_styles()

    def _register_chinese_font(self) -> None:
        """注册中文字体"""
        self.chinese_font_name = "ChineseFont"
        
        # 尝试找到可用的中文字体
        for font_path in self.CHINESE_FONT_PATHS:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(self.chinese_font_name, font_path))
                    return
                except Exception:
                    continue
        
        # 如果找不到中文字体，使用默认字体
        self.chinese_font_name = "Helvetica"

    def _create_styles(self) -> None:
        """创建PDF样式"""
        self.styles = getSampleStyleSheet()
        
        # 原文样式（英文）
        self.original_style = ParagraphStyle(
            "Original",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=self.font_size,
            leading=self.font_size * self.line_spacing,
            textColor=colors.black,
            spaceAfter=6,
        )
        
        # 译文样式（中文）
        self.translated_style = ParagraphStyle(
            "Translated",
            parent=self.styles["Normal"],
            fontName=self.chinese_font_name,
            fontSize=self.font_size,
            leading=self.font_size * self.line_spacing,
            textColor=colors.HexColor("#333333"),
            spaceAfter=6,
        )
        
        # 标题样式
        self.title_style = ParagraphStyle(
            "Title",
            parent=self.styles["Heading1"],
            fontName=self.chinese_font_name,
            fontSize=16,
            textColor=colors.HexColor("#1a1a1a"),
            spaceAfter=20,
            alignment=1,  # 居中
        )
        
        # 页码标题样式
        self.page_header_style = ParagraphStyle(
            "PageHeader",
            parent=self.styles["Heading2"],
            fontName=self.chinese_font_name,
            fontSize=12,
            textColor=colors.HexColor("#666666"),
            spaceBefore=15,
            spaceAfter=10,
        )

    def generate_dual_column_pdf(
        self,
        contents: List[BilingualContent],
        output_path: str | Path,
        title: Optional[str] = None,
    ) -> None:
        """生成左右双栏对照PDF
        
        Args:
            contents: 双语内容列表
            output_path: 输出文件路径
            title: 文档标题
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        # 构建内容
        elements = []
        
        # 添加标题
        if title:
            elements.append(Paragraph(title, self.title_style))
            elements.append(Spacer(1, 20))

        # 计算列宽
        page_width = self.page_size[0] - 2 * self.margin
        col_width = (page_width - 10) / 2  # 留10点间距

        # 按页组织内容
        current_page = -1
        for content in contents:
            if content.page_num != current_page:
                current_page = content.page_num
                elements.append(Paragraph(
                    f"第 {current_page + 1} 页",
                    self.page_header_style
                ))

            # 创建双栏表格
            original_para = Paragraph(
                self._escape_html(content.original),
                self.original_style
            )
            translated_para = Paragraph(
                self._escape_html(content.translated),
                self.translated_style
            )

            table = Table(
                [[original_para, translated_para]],
                colWidths=[col_width, col_width],
            )
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 10))

        # 生成PDF
        doc.build(elements)

    def generate_interleaved_pdf(
        self,
        contents: List[BilingualContent],
        output_path: str | Path,
        title: Optional[str] = None,
    ) -> None:
        """生成上下交替对照PDF
        
        Args:
            contents: 双语内容列表
            output_path: 输出文件路径
            title: 文档标题
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        elements = []
        
        # 添加标题
        if title:
            elements.append(Paragraph(title, self.title_style))
            elements.append(Spacer(1, 20))

        # 原文块样式（带背景色）
        original_block_style = ParagraphStyle(
            "OriginalBlock",
            parent=self.original_style,
            backColor=colors.HexColor("#f5f5f5"),
            borderPadding=8,
        )

        # 按页组织内容
        current_page = -1
        for content in contents:
            if content.page_num != current_page:
                current_page = content.page_num
                elements.append(Paragraph(
                    f"第 {current_page + 1} 页",
                    self.page_header_style
                ))

            # 原文
            elements.append(Paragraph(
                self._escape_html(content.original),
                original_block_style
            ))
            elements.append(Spacer(1, 5))
            
            # 译文
            elements.append(Paragraph(
                self._escape_html(content.translated),
                self.translated_style
            ))
            elements.append(Spacer(1, 15))

        # 生成PDF
        doc.build(elements)

    def generate_translation_only_pdf(
        self,
        contents: List[BilingualContent],
        output_path: str | Path,
        title: Optional[str] = None,
    ) -> None:
        """生成仅译文PDF
        
        Args:
            contents: 双语内容列表
            output_path: 输出文件路径
            title: 文档标题
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin,
        )

        elements = []
        
        if title:
            elements.append(Paragraph(title, self.title_style))
            elements.append(Spacer(1, 20))

        current_page = -1
        for content in contents:
            if content.page_num != current_page:
                current_page = content.page_num
                elements.append(Paragraph(
                    f"第 {current_page + 1} 页",
                    self.page_header_style
                ))

            elements.append(Paragraph(
                self._escape_html(content.translated),
                self.translated_style
            ))
            elements.append(Spacer(1, 10))

        doc.build(elements)

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符
        
        Args:
            text: 原始文本
            
        Returns:
            转义后的文本
        """
        if not text:
            return ""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

