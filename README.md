# AI Translater - PDF OCR翻译工具

从扫描PDF中提取文字并翻译成中文，生成双语对照PDF。

## 功能特性

- 📄 **PDF文字提取**: 使用PyMuPDF将PDF页面转换为高清图片
- 🔍 **OCR识别**: 使用PaddleOCR进行文字识别，支持英文和多语言
- 🌐 **AI翻译**: 使用OpenAI API进行高质量的英译中翻译
- 📝 **双语PDF生成**: 生成左右双栏或上下交替的双语对照PDF

## 安装

### 前置要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - Python包管理工具
- poppler (用于PDF处理)

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Windows
# 下载并安装 https://github.com/oschwartz10612/poppler-windows
```

### 安装项目

```bash
# 克隆项目
cd ai-translater

# 使用uv安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

## 配置

创建 `.env` 文件配置API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，使用代理时设置
OPENAI_MODEL=gpt-4o-mini  # 可选，默认gpt-4o-mini
```

## 使用方法

### 命令行使用

```bash
# 基本使用 - 生成左右双栏对照PDF
ai-translater input.pdf output.pdf

# 指定输出格式
ai-translater input.pdf output.pdf --format interleaved  # 上下交替
ai-translater input.pdf output.pdf --format translation  # 仅译文

# 指定页面范围
ai-translater input.pdf output.pdf --pages 1-5

# 添加文档标题
ai-translater input.pdf output.pdf --title "文档翻译"

# 仅提取文本（不翻译）
ai-translater input.pdf output.txt --extract-only

# 使用自定义API配置
ai-translater input.pdf output.pdf --api-key YOUR_KEY --base-url https://api.example.com/v1
```

### Python代码使用

```python
from ai_translater import PDFTranslator, OutputFormat

# 创建翻译器
translator = PDFTranslator(
    openai_api_key="your-api-key",  # 或设置环境变量
)

# 处理PDF
translator.process(
    input_pdf="scanned_doc.pdf",
    output_pdf="translated_doc.pdf",
    output_format=OutputFormat.DUAL_COLUMN,
    title="文档翻译",
)

# 仅提取文本
text = translator.extract_text("input.pdf")
print(text)
```

### 单独使用各模块

```python
from ai_translater import PDFExtractor, OCREngine, Translator, PDFGenerator

# PDF提取
extractor = PDFExtractor(dpi=300)
images = extractor.extract_pages("input.pdf")

# OCR识别
ocr = OCREngine(lang="en")
results = ocr.recognize_batch(images)

# 翻译
translator = Translator()
translation = translator.translate("Hello, world!")
print(translation.translated)

# 生成PDF
generator = PDFGenerator()
generator.generate_dual_column_pdf(contents, "output.pdf")
```

## 输出格式

| 格式 | 说明 |
|------|------|
| `dual` | 左右双栏对照，左侧原文右侧译文 |
| `interleaved` | 上下交替，原文和译文交替显示 |
| `translation` | 仅显示翻译后的文本 |

## 项目结构

```
ai-translater/
├── pyproject.toml          # 项目配置
├── src/
│   └── ai_translater/
│       ├── __init__.py     # 模块导出
│       ├── main.py         # 主入口和CLI
│       ├── pdf_extractor.py # PDF转图片
│       ├── ocr_engine.py   # OCR识别
│       ├── translator.py   # AI翻译
│       └── pdf_generator.py # PDF生成
└── tests/                  # 测试目录
```

## 许可证

MIT License

