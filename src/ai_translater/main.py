"""主入口模块 - PDF OCR翻译工具

支持分步执行：
1. extract: PDF转图片
2. ocr: 图片OCR识别
3. translate: 翻译OCR结果
4. generate: 生成双语PDF
5. all: 完整流程
"""

import argparse
import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from .ocr_engine import OCREngine, PageOCRResult, TextBlock
from .pdf_extractor import PDFExtractor
from .pdf_generator import BilingualContent, PDFGenerator
from .translator import Translator
from .word_generator import WordGenerator


class OutputFormat(str, Enum):
    """输出格式"""
    DUAL_COLUMN = "dual"  # 左右双栏
    INTERLEAVED = "interleaved"  # 上下交替
    TRANSLATION_ONLY = "translation"  # 仅译文


# ============== 步骤1: 提取图片 ==============

def cmd_extract(args):
    """执行PDF提取图片"""
    load_dotenv()
    
    input_pdf = Path(args.input)
    output_dir = Path(args.output_dir)
    
    if not args.quiet:
        print(f"📄 正在处理: {input_pdf}")
    
    # 解析页面范围
    page_range = parse_page_range(args.pages)
    
    # 提取图片
    extractor = PDFExtractor(dpi=args.dpi)
    
    if not args.quiet:
        print("🖼️  正在提取PDF页面...")
    
    images = extractor.extract_pages(input_pdf, output_dir=output_dir, page_range=page_range)
    
    if not args.quiet:
        print(f"✅ 提取了 {len(images)} 页到 {output_dir}")


# ============== 步骤2: OCR识别 ==============

def cmd_ocr(args):
    """执行OCR识别"""
    load_dotenv()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not args.quiet:
        print(f"📂 输入目录: {input_dir}")
    
    # 获取所有图片文件
    image_files = sorted(input_dir.glob("*.png")) + sorted(input_dir.glob("*.jpg"))
    
    if not image_files:
        print("❌ 未找到图片文件", file=sys.stderr)
        sys.exit(1)
    
    if not args.quiet:
        print(f"🔍 正在进行OCR识别 ({len(image_files)} 张图片)...")
    
    # OCR识别
    ocr = OCREngine(lang=args.lang)
    
    for i, img_path in enumerate(image_files):
        if not args.quiet:
            print(f"   识别第 {i + 1}/{len(image_files)} 张: {img_path.name}")
        
        result = ocr.recognize(str(img_path), page_num=i)
        
        # 保存结果
        page_data = {
            "page": i + 1,
            "source_file": img_path.stem,
            "image_file": img_path.name,
            "text_blocks": [
                {
                    "text": block.text,
                    "confidence": block.confidence,
                    "bbox": block.bbox,
                    "position": {
                        "x": block.x,
                        "y": block.y,
                        "width": block.width,
                        "height": block.height,
                    }
                }
                for block in result.text_blocks
            ],
            "full_text": result.full_text,
            "text_block_count": len(result.text_blocks),
        }
        
        output_file = output_dir / f"page_{i + 1:04d}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    if not args.quiet:
        print(f"✅ OCR结果已保存到 {output_dir}")


# ============== 步骤3: 翻译 ==============

# 页面分隔标记
PAGE_SEPARATOR = "\n\n---PAGE_BREAK---\n\n"


def cmd_translate(args):
    """执行翻译 - 全文合并翻译，保持跨页句子完整性"""
    load_dotenv()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not args.quiet:
        print(f"📂 输入目录: {input_dir}")
    
    # 获取所有OCR结果文件
    json_files = sorted(input_dir.glob("*.json"))
    
    if not json_files:
        print("❌ 未找到OCR结果文件", file=sys.stderr)
        sys.exit(1)
    
    # 读取所有OCR结果
    ocr_data_list = []
    page_texts = []
    
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)
        ocr_data_list.append((json_file, ocr_data))
        page_texts.append(ocr_data.get("full_text", "").strip())
    
    # 合并所有页面文本
    merged_text = PAGE_SEPARATOR.join(page_texts)
    
    if not merged_text.strip():
        if not args.quiet:
            print("⚠️ 没有找到需要翻译的文本")
        # 保存空结果
        for json_file, ocr_data in ocr_data_list:
            translation_data = {**ocr_data, "translated_text": ""}
            output_file = output_dir / json_file.name
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(translation_data, f, ensure_ascii=False, indent=2)
        return
    
    # 初始化翻译器
    translator = Translator(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
    )
    
    if not args.quiet:
        print(f"🌐 正在翻译 ({len(json_files)} 页，全文合并模式)...")
    
    # 全文翻译（带页面分隔标记）
    translated_text = translate_with_page_breaks(
        translator, 
        merged_text, 
        len(json_files),
        verbose=not args.quiet
    )
    
    # 按标记拆分翻译结果
    translated_pages = translated_text.split("---PAGE_BREAK---")
    translated_pages = [p.strip() for p in translated_pages]
    
    # 确保页数匹配
    while len(translated_pages) < len(json_files):
        translated_pages.append("")
    
    # 保存翻译结果
    for i, (json_file, ocr_data) in enumerate(ocr_data_list):
        translated = translated_pages[i] if i < len(translated_pages) else ""
        
        translation_data = {
            **ocr_data,
            "translated_text": translated,
        }
        
        output_file = output_dir / json_file.name
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(translation_data, f, ensure_ascii=False, indent=2)
    
    if not args.quiet:
        print(f"✅ 翻译结果已保存到 {output_dir}")


def translate_with_page_breaks(
    translator: Translator,
    text: str,
    page_count: int,
    max_chars_per_batch: int = 8000,
    verbose: bool = True,
) -> str:
    """翻译带页面分隔标记的文本
    
    Args:
        translator: 翻译器实例
        text: 带PAGE_BREAK标记的合并文本
        page_count: 页数
        max_chars_per_batch: 每批最大字符数
        verbose: 是否输出详细信息
        
    Returns:
        翻译后的文本（保留PAGE_BREAK标记）
    """
    # 构建特殊的翻译提示
    context = f"""This is a document with {page_count} pages. 
Pages are separated by "---PAGE_BREAK---" markers.
IMPORTANT: You must preserve all "---PAGE_BREAK---" markers in your translation exactly as they appear.
Translate the content between markers while keeping the markers intact."""
    
    # 如果文本不太长，直接翻译
    if len(text) <= max_chars_per_batch:
        if verbose:
            print(f"   翻译全文 ({len(text)} 字符)...")
        result = translator.translate(text, context=context)
        return result.translated
    
    # 文本太长，按页面分隔标记分批翻译
    if verbose:
        print(f"   文本较长 ({len(text)} 字符)，分批翻译...")
    
    pages = text.split(PAGE_SEPARATOR)
    translated_pages = []
    
    current_batch = []
    current_length = 0
    
    for i, page in enumerate(pages):
        page_length = len(page) + len(PAGE_SEPARATOR)
        
        # 如果当前批次加上这页会超过限制，先翻译当前批次
        if current_length + page_length > max_chars_per_batch and current_batch:
            batch_text = PAGE_SEPARATOR.join(current_batch)
            if verbose:
                print(f"   翻译批次 ({len(current_batch)} 页)...")
            result = translator.translate(batch_text, context=context)
            
            # 拆分翻译结果
            batch_translated = result.translated.split("---PAGE_BREAK---")
            translated_pages.extend([p.strip() for p in batch_translated])
            
            current_batch = []
            current_length = 0
        
        current_batch.append(page)
        current_length += page_length
    
    # 翻译最后一批
    if current_batch:
        batch_text = PAGE_SEPARATOR.join(current_batch)
        if verbose:
            print(f"   翻译批次 ({len(current_batch)} 页)...")
        result = translator.translate(batch_text, context=context)
        
        batch_translated = result.translated.split("---PAGE_BREAK---")
        translated_pages.extend([p.strip() for p in batch_translated])
    
    return "\n\n---PAGE_BREAK---\n\n".join(translated_pages)


# ============== 步骤4: 生成文档 ==============

def cmd_generate(args):
    """生成双语文档（PDF或Word）"""
    load_dotenv()
    
    input_dir = Path(args.input_dir)
    output_file = Path(args.output)
    
    if not args.quiet:
        print(f"📂 输入目录: {input_dir}")
    
    # 获取所有翻译结果文件
    json_files = sorted(input_dir.glob("*.json"))
    
    if not json_files:
        print("❌ 未找到翻译结果文件", file=sys.stderr)
        sys.exit(1)
    
    # 读取翻译结果
    contents: List[BilingualContent] = []
    
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        original = data.get("full_text", "")
        translated = data.get("translated_text", "")
        page_num = data.get("page", 1) - 1  # 转为0-based
        
        if original or translated:
            contents.append(BilingualContent(
                original=original,
                translated=translated,
                page_num=page_num,
            ))
    
    # 根据扩展名选择输出格式
    is_word = output_file.suffix.lower() in ['.docx', '.doc']
    output_format = OutputFormat(args.format)
    
    if is_word:
        if not args.quiet:
            print(f"📝 正在生成双语Word文档 ({len(contents)} 页)...")
        
        generator = WordGenerator()
        
        if output_format == OutputFormat.DUAL_COLUMN:
            generator.generate_dual_column_docx(contents, output_file, args.title)
        elif output_format == OutputFormat.INTERLEAVED:
            generator.generate_interleaved_docx(contents, output_file, args.title)
        else:
            generator.generate_translation_only_docx(contents, output_file, args.title)
        
        if not args.quiet:
            print(f"✅ Word文档已生成: {output_file}")
    else:
        if not args.quiet:
            print(f"📝 正在生成双语PDF ({len(contents)} 页)...")
        
        generator = PDFGenerator()
        
        if output_format == OutputFormat.DUAL_COLUMN:
            generator.generate_dual_column_pdf(contents, output_file, args.title)
        elif output_format == OutputFormat.INTERLEAVED:
            generator.generate_interleaved_pdf(contents, output_file, args.title)
        else:
            generator.generate_translation_only_pdf(contents, output_file, args.title)
        
        if not args.quiet:
            print(f"✅ PDF已生成: {output_file}")


# ============== 步骤5: 完整流程 ==============

def cmd_all(args):
    """执行完整流程"""
    load_dotenv()
    
    input_pdf = Path(args.input)
    output_pdf = Path(args.output)
    work_dir = Path(args.work_dir) if args.work_dir else output_pdf.parent / f".{output_pdf.stem}_work"
    
    # 创建工作目录
    images_dir = work_dir / "images"
    ocr_dir = work_dir / "ocr_results"
    translations_dir = work_dir / "translations"
    
    images_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir.mkdir(parents=True, exist_ok=True)
    translations_dir.mkdir(parents=True, exist_ok=True)
    
    page_range = parse_page_range(args.pages)
    verbose = not args.quiet
    
    if verbose:
        print(f"📄 正在处理: {input_pdf}")
        print(f"📁 工作目录: {work_dir}")
    
    # 步骤1: 提取图片
    if verbose:
        print("\n🖼️  [1/4] 正在提取PDF页面...")
    
    extractor = PDFExtractor(dpi=args.dpi)
    images = extractor.extract_pages(input_pdf, output_dir=images_dir, page_range=page_range)
    
    if verbose:
        print(f"   提取了 {len(images)} 页")
    
    # 步骤2: OCR识别
    if verbose:
        print("\n🔍 [2/4] 正在进行OCR识别...")
    
    ocr = OCREngine(lang=args.lang)
    image_files = sorted(images_dir.glob("*.png"))
    
    for i, img_path in enumerate(image_files):
        if verbose:
            print(f"   识别第 {i + 1}/{len(image_files)} 页...")
        
        result = ocr.recognize(str(img_path), page_num=i)
        
        page_data = {
            "page": i + 1,
            "source_file": input_pdf.stem,
            "image_file": img_path.name,
            "text_blocks": [
                {
                    "text": block.text,
                    "confidence": block.confidence,
                    "bbox": block.bbox,
                    "position": {
                        "x": block.x,
                        "y": block.y,
                        "width": block.width,
                        "height": block.height,
                    }
                }
                for block in result.text_blocks
            ],
            "full_text": result.full_text,
            "text_block_count": len(result.text_blocks),
        }
        
        output_file = ocr_dir / f"page_{i + 1:04d}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)
    
    # 步骤3: 翻译（全文合并模式）
    if verbose:
        print("\n🌐 [3/4] 正在翻译（全文合并模式）...")
    
    translator = Translator(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
    )
    
    json_files = sorted(ocr_dir.glob("*.json"))
    
    # 读取所有OCR结果
    ocr_data_list = []
    page_texts = []
    
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)
        ocr_data_list.append((json_file, ocr_data))
        page_texts.append(ocr_data.get("full_text", "").strip())
    
    # 合并所有页面文本
    merged_text = PAGE_SEPARATOR.join(page_texts)
    
    if merged_text.strip():
        # 全文翻译
        translated_text = translate_with_page_breaks(
            translator, 
            merged_text, 
            len(json_files),
            verbose=verbose
        )
        
        # 按标记拆分翻译结果
        translated_pages = translated_text.split("---PAGE_BREAK---")
        translated_pages = [p.strip() for p in translated_pages]
    else:
        translated_pages = [""] * len(json_files)
    
    # 确保页数匹配
    while len(translated_pages) < len(json_files):
        translated_pages.append("")
    
    # 保存翻译结果
    for i, (json_file, ocr_data) in enumerate(ocr_data_list):
        translated = translated_pages[i] if i < len(translated_pages) else ""
        
        translation_data = {
            **ocr_data,
            "translated_text": translated,
        }
        
        output_file = translations_dir / json_file.name
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(translation_data, f, ensure_ascii=False, indent=2)
    
    # 步骤4: 生成文档（PDF或Word）
    is_word = output_pdf.suffix.lower() in ['.docx', '.doc']
    doc_type = "Word文档" if is_word else "PDF"
    
    if verbose:
        print(f"\n📝 [4/4] 正在生成双语{doc_type}...")
    
    contents: List[BilingualContent] = []
    translation_files = sorted(translations_dir.glob("*.json"))
    
    for json_file in translation_files:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        original = data.get("full_text", "")
        translated = data.get("translated_text", "")
        page_num = data.get("page", 1) - 1
        
        if original or translated:
            contents.append(BilingualContent(
                original=original,
                translated=translated,
                page_num=page_num,
            ))
    
    output_format = OutputFormat(args.format)
    
    if is_word:
        generator = WordGenerator()
        if output_format == OutputFormat.DUAL_COLUMN:
            generator.generate_dual_column_docx(contents, output_pdf, args.title)
        elif output_format == OutputFormat.INTERLEAVED:
            generator.generate_interleaved_docx(contents, output_pdf, args.title)
        else:
            generator.generate_translation_only_docx(contents, output_pdf, args.title)
    else:
        generator = PDFGenerator()
        if output_format == OutputFormat.DUAL_COLUMN:
            generator.generate_dual_column_pdf(contents, output_pdf, args.title)
        elif output_format == OutputFormat.INTERLEAVED:
            generator.generate_interleaved_pdf(contents, output_pdf, args.title)
        else:
            generator.generate_translation_only_pdf(contents, output_pdf, args.title)
    
    if verbose:
        print(f"\n✅ 完成！输出文件: {output_pdf}")
        print(f"   中间文件保存在: {work_dir}")


# ============== 辅助函数 ==============

def parse_page_range(pages_str: Optional[str]) -> Optional[tuple]:
    """解析页面范围字符串"""
    if not pages_str:
        return None
    
    if "-" in pages_str:
        start, end = pages_str.split("-")
        return (int(start) - 1, int(end))
    else:
        page_num = int(pages_str) - 1
        return (page_num, page_num + 1)


# ============== CLI入口 ==============

def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        description="PDF OCR翻译工具 - 从扫描PDF中提取文字并翻译",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # ---- extract 子命令 ----
    extract_parser = subparsers.add_parser(
        "extract",
        help="从PDF提取图片",
        description="将PDF每页转换为图片文件",
    )
    extract_parser.add_argument("input", help="输入PDF文件路径")
    extract_parser.add_argument("--output-dir", "-o", required=True, help="输出图片目录")
    extract_parser.add_argument("--pages", "-p", help="页面范围，如 '1-5' 或 '3'")
    extract_parser.add_argument("--dpi", type=int, default=300, help="图片DPI，默认300")
    extract_parser.add_argument("-q", "--quiet", action="store_true", help="安静模式")
    extract_parser.set_defaults(func=cmd_extract)
    
    # ---- ocr 子命令 ----
    ocr_parser = subparsers.add_parser(
        "ocr",
        help="对图片进行OCR识别",
        description="识别图片中的文字，输出JSON格式结果",
    )
    ocr_parser.add_argument("--input-dir", "-i", required=True, help="输入图片目录")
    ocr_parser.add_argument("--output-dir", "-o", required=True, help="输出OCR结果目录")
    ocr_parser.add_argument("--lang", default="en", help="识别语言，默认en")
    ocr_parser.add_argument("-q", "--quiet", action="store_true", help="安静模式")
    ocr_parser.set_defaults(func=cmd_ocr)
    
    # ---- translate 子命令 ----
    translate_parser = subparsers.add_parser(
        "translate",
        help="翻译OCR结果",
        description="读取OCR结果JSON文件，使用AI进行翻译",
    )
    translate_parser.add_argument("--input-dir", "-i", required=True, help="输入OCR结果目录")
    translate_parser.add_argument("--output-dir", "-o", required=True, help="输出翻译结果目录")
    translate_parser.add_argument("--api-key", help="OpenAI API密钥")
    translate_parser.add_argument("--base-url", help="OpenAI API基础URL")
    translate_parser.add_argument("--model", help="使用的模型，默认gpt-4o-mini")
    translate_parser.add_argument("-q", "--quiet", action="store_true", help="安静模式")
    translate_parser.set_defaults(func=cmd_translate)
    
    # ---- generate 子命令 ----
    generate_parser = subparsers.add_parser(
        "generate",
        help="生成双语PDF",
        description="从翻译结果生成双语对照PDF",
    )
    generate_parser.add_argument("--input-dir", "-i", required=True, help="输入翻译结果目录")
    generate_parser.add_argument("--output", "-o", required=True, help="输出PDF文件路径")
    generate_parser.add_argument("--format", "-f", choices=["dual", "interleaved", "translation"],
                                 default="dual", help="输出格式")
    generate_parser.add_argument("--title", "-t", help="PDF文档标题")
    generate_parser.add_argument("-q", "--quiet", action="store_true", help="安静模式")
    generate_parser.set_defaults(func=cmd_generate)
    
    # ---- all 子命令 ----
    all_parser = subparsers.add_parser(
        "all",
        help="执行完整流程",
        description="从PDF到双语PDF的完整流程",
        epilog="""
示例:
  ai-translater all input.pdf output.pdf
  ai-translater all input.pdf output.pdf --format interleaved
  ai-translater all input.pdf output.pdf --pages 1-5
  ai-translater all input.pdf output.pdf --work-dir ./work/
        """,
    )
    all_parser.add_argument("input", help="输入PDF文件路径")
    all_parser.add_argument("output", help="输出PDF文件路径")
    all_parser.add_argument("--format", "-f", choices=["dual", "interleaved", "translation"],
                            default="dual", help="输出格式")
    all_parser.add_argument("--pages", "-p", help="页面范围，如 '1-5' 或 '3'")
    all_parser.add_argument("--title", "-t", help="PDF文档标题")
    all_parser.add_argument("--work-dir", "-w", help="工作目录，存放中间文件")
    all_parser.add_argument("--dpi", type=int, default=300, help="图片DPI，默认300")
    all_parser.add_argument("--lang", default="en", help="OCR识别语言，默认en")
    all_parser.add_argument("--api-key", help="OpenAI API密钥")
    all_parser.add_argument("--base-url", help="OpenAI API基础URL")
    all_parser.add_argument("--model", help="使用的模型，默认gpt-4o-mini")
    all_parser.add_argument("-q", "--quiet", action="store_true", help="安静模式")
    all_parser.set_defaults(func=cmd_all)
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        args.func(args)
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
