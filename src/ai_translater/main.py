"""主入口模块 - PDF OCR翻译工具"""

import argparse
import os
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from .ocr_engine import OCREngine, PageOCRResult
from .pdf_extractor import PDFExtractor
from .pdf_generator import BilingualContent, PDFGenerator
from .translator import Translator


class OutputFormat(str, Enum):
    """输出格式"""
    DUAL_COLUMN = "dual"  # 左右双栏
    INTERLEAVED = "interleaved"  # 上下交替
    TRANSLATION_ONLY = "translation"  # 仅译文


class PDFTranslator:
    """PDF翻译器 - 整合所有模块的主类"""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        openai_model: Optional[str] = None,
        source_lang: str = "English",
        target_lang: str = "Chinese",
        ocr_lang: str = "en",
        dpi: int = 300,
    ):
        """初始化PDF翻译器
        
        Args:
            openai_api_key: OpenAI API密钥
            openai_base_url: OpenAI API基础URL
            openai_model: 使用的模型
            source_lang: 源语言
            target_lang: 目标语言
            ocr_lang: OCR识别语言
            dpi: PDF转图片的DPI
        """
        # 加载环境变量
        load_dotenv()
        
        # 初始化各模块
        self.extractor = PDFExtractor(dpi=dpi)
        self.ocr = OCREngine(lang=ocr_lang)
        self.translator = Translator(
            api_key=openai_api_key,
            base_url=openai_base_url,
            model=openai_model,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        self.generator = PDFGenerator()

    def process(
        self,
        input_pdf: str | Path,
        output_pdf: str | Path,
        output_format: OutputFormat = OutputFormat.DUAL_COLUMN,
        title: Optional[str] = None,
        page_range: Optional[tuple[int, int]] = None,
        verbose: bool = True,
    ) -> None:
        """处理PDF文件
        
        Args:
            input_pdf: 输入PDF路径
            output_pdf: 输出PDF路径
            output_format: 输出格式
            title: 文档标题
            page_range: 页面范围
            verbose: 是否输出详细信息
        """
        input_pdf = Path(input_pdf)
        output_pdf = Path(output_pdf)

        if verbose:
            print(f"📄 正在处理: {input_pdf}")

        # 1. 提取PDF页面为图片
        if verbose:
            print("🖼️  正在提取PDF页面...")
        images = self.extractor.extract_pages(input_pdf, page_range=page_range)
        
        if verbose:
            print(f"   提取了 {len(images)} 页")

        # 2. OCR识别
        if verbose:
            print("🔍 正在进行OCR识别...")
        ocr_results = self._perform_ocr(images, verbose)

        # 3. 翻译
        if verbose:
            print("🌐 正在翻译...")
        bilingual_contents = self._translate(ocr_results, verbose)

        # 4. 生成PDF
        if verbose:
            print("📝 正在生成双语PDF...")
        self._generate_pdf(
            bilingual_contents,
            output_pdf,
            output_format,
            title,
        )

        if verbose:
            print(f"✅ 完成！输出文件: {output_pdf}")

    def _perform_ocr(
        self,
        images: list,
        verbose: bool = True,
    ) -> List[PageOCRResult]:
        """对图片进行OCR识别"""
        results = []
        for i, img in enumerate(images):
            if verbose:
                print(f"   识别第 {i + 1}/{len(images)} 页...")
            result = self.ocr.recognize(img, page_num=i)
            results.append(result)
        return results

    def _translate(
        self,
        ocr_results: List[PageOCRResult],
        verbose: bool = True,
    ) -> List[BilingualContent]:
        """翻译OCR结果"""
        contents = []
        for result in ocr_results:
            if not result.has_text:
                continue
                
            if verbose:
                print(f"   翻译第 {result.page_num + 1} 页...")
            
            # 翻译整页文本
            translation = self.translator.translate_paragraphs(result.full_text)
            
            contents.append(BilingualContent(
                original=result.full_text,
                translated=translation.translated,
                page_num=result.page_num,
            ))
        
        return contents

    def _generate_pdf(
        self,
        contents: List[BilingualContent],
        output_path: Path,
        output_format: OutputFormat,
        title: Optional[str],
    ) -> None:
        """生成PDF文件"""
        if output_format == OutputFormat.DUAL_COLUMN:
            self.generator.generate_dual_column_pdf(contents, output_path, title)
        elif output_format == OutputFormat.INTERLEAVED:
            self.generator.generate_interleaved_pdf(contents, output_path, title)
        else:
            self.generator.generate_translation_only_pdf(contents, output_path, title)

    def extract_text(
        self,
        input_pdf: str | Path,
        output_file: Optional[str | Path] = None,
        page_range: Optional[tuple[int, int]] = None,
    ) -> str:
        """仅提取PDF中的文本
        
        Args:
            input_pdf: 输入PDF路径
            output_file: 可选的输出文本文件路径
            page_range: 页面范围
            
        Returns:
            提取的文本
        """
        images = self.extractor.extract_pages(input_pdf, page_range=page_range)
        ocr_results = self.ocr.recognize_batch(images)
        
        full_text = "\n\n".join(
            f"--- 第 {r.page_num + 1} 页 ---\n{r.full_text}"
            for r in ocr_results
            if r.has_text
        )
        
        if output_file:
            Path(output_file).write_text(full_text, encoding="utf-8")
        
        return full_text


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        description="PDF OCR翻译工具 - 从扫描PDF中提取文字并翻译",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  ai-translater input.pdf output.pdf
  ai-translater input.pdf output.pdf --format interleaved
  ai-translater input.pdf output.pdf --pages 1-5
  ai-translater input.pdf --extract-only output.txt
        """,
    )
    
    parser.add_argument(
        "input",
        help="输入PDF文件路径",
    )
    parser.add_argument(
        "output",
        help="输出文件路径（PDF或TXT）",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["dual", "interleaved", "translation"],
        default="dual",
        help="输出格式: dual(左右双栏), interleaved(上下交替), translation(仅译文)",
    )
    parser.add_argument(
        "-p", "--pages",
        help="页面范围，如 '1-5' 或 '3'",
    )
    parser.add_argument(
        "-t", "--title",
        help="PDF文档标题",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="仅提取文本，不翻译",
    )
    parser.add_argument(
        "--api-key",
        help="OpenAI API密钥（或设置OPENAI_API_KEY环境变量）",
    )
    parser.add_argument(
        "--base-url",
        help="OpenAI API基础URL",
    )
    parser.add_argument(
        "--model",
        help="使用的模型，默认gpt-4o-mini",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="PDF转图片的DPI，默认300",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="安静模式，不输出详细信息",
    )

    args = parser.parse_args()

    # 解析页面范围
    page_range = None
    if args.pages:
        if "-" in args.pages:
            start, end = args.pages.split("-")
            page_range = (int(start) - 1, int(end))  # 转换为0-based
        else:
            page_num = int(args.pages) - 1
            page_range = (page_num, page_num + 1)

    try:
        translator = PDFTranslator(
            openai_api_key=args.api_key,
            openai_base_url=args.base_url,
            openai_model=args.model,
            dpi=args.dpi,
        )

        if args.extract_only:
            # 仅提取文本
            text = translator.extract_text(
                args.input,
                args.output,
                page_range=page_range,
            )
            if not args.quiet:
                print(f"✅ 文本已提取到: {args.output}")
        else:
            # 完整的翻译流程
            output_format = OutputFormat(args.format)
            translator.process(
                input_pdf=args.input,
                output_pdf=args.output,
                output_format=output_format,
                title=args.title,
                page_range=page_range,
                verbose=not args.quiet,
            )

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"❌ 配置错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 处理失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

