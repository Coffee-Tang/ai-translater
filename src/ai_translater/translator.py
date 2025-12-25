"""翻译模块 - 使用OpenAI API进行文本翻译"""

import os
import time
from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI


@dataclass
class TranslationResult:
    """翻译结果"""
    original: str  # 原文
    translated: str  # 译文
    source_lang: str  # 源语言
    target_lang: str  # 目标语言


class Translator:
    """翻译器 - 使用OpenAI API进行翻译"""

    DEFAULT_MODEL = "gpt-4o-mini"
    MAX_TOKENS_PER_REQUEST = 4000  # 每次请求的最大token数
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        source_lang: str = "English",
        target_lang: str = "Chinese",
    ):
        """初始化翻译器
        
        Args:
            api_key: OpenAI API密钥，默认从环境变量OPENAI_API_KEY获取
            base_url: API基础URL，默认从环境变量OPENAI_BASE_URL获取
            model: 使用的模型，默认gpt-4o-mini
            source_lang: 源语言
            target_lang: 目标语言
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model or os.getenv("OPENAI_MODEL", self.DEFAULT_MODEL)
        self.source_lang = source_lang
        self.target_lang = target_lang
        
        if not self.api_key:
            raise ValueError("OpenAI API密钥未设置，请设置OPENAI_API_KEY环境变量或传入api_key参数")

        # 初始化OpenAI客户端
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
            
        self.client = OpenAI(**client_kwargs)

    def translate(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        context: Optional[str] = None,
    ) -> TranslationResult:
        """翻译文本
        
        Args:
            text: 要翻译的文本
            source_lang: 源语言，默认使用初始化时设置的语言
            target_lang: 目标语言，默认使用初始化时设置的语言
            context: 上下文信息，帮助提高翻译质量
            
        Returns:
            TranslationResult对象
        """
        source = source_lang or self.source_lang
        target = target_lang or self.target_lang
        
        if not text.strip():
            return TranslationResult(
                original=text,
                translated=text,
                source_lang=source,
                target_lang=target,
            )

        # 构建翻译提示词
        system_prompt = self._build_system_prompt(source, target, context)
        
        # 调用API
        translated = self._call_api(system_prompt, text)

        return TranslationResult(
            original=text,
            translated=translated,
            source_lang=source,
            target_lang=target,
        )

    def translate_batch(
        self,
        texts: List[str],
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        delay: float = 0.5,
    ) -> List[TranslationResult]:
        """批量翻译文本
        
        Args:
            texts: 要翻译的文本列表
            source_lang: 源语言
            target_lang: 目标语言
            delay: 每次请求之间的延迟（秒），避免速率限制
            
        Returns:
            TranslationResult列表
        """
        results = []
        for i, text in enumerate(texts):
            result = self.translate(text, source_lang, target_lang)
            results.append(result)
            
            # 添加延迟避免速率限制
            if i < len(texts) - 1:
                time.sleep(delay)
                
        return results

    def translate_paragraphs(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> TranslationResult:
        """按段落翻译长文本
        
        将长文本拆分成段落，分别翻译后合并
        
        Args:
            text: 要翻译的长文本
            source_lang: 源语言
            target_lang: 目标语言
            
        Returns:
            TranslationResult对象
        """
        source = source_lang or self.source_lang
        target = target_lang or self.target_lang

        # 按段落拆分
        paragraphs = text.split("\n\n")
        
        # 合并短段落以减少API调用
        chunks = self._merge_short_paragraphs(paragraphs)
        
        # 翻译每个块
        translated_chunks = []
        for chunk in chunks:
            result = self.translate(chunk, source, target)
            translated_chunks.append(result.translated)
            time.sleep(0.3)  # 短暂延迟

        # 合并翻译结果
        translated = "\n\n".join(translated_chunks)

        return TranslationResult(
            original=text,
            translated=translated,
            source_lang=source,
            target_lang=target,
        )

    def _build_system_prompt(
        self,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
    ) -> str:
        """构建系统提示词
        
        Args:
            source_lang: 源语言
            target_lang: 目标语言
            context: 上下文信息
            
        Returns:
            系统提示词
        """
        prompt = f"""You are a professional translator. Translate the following text from {source_lang} to {target_lang}.

Requirements:
1. Maintain the original meaning and tone
2. Use natural and fluent {target_lang} expressions
3. Preserve any formatting, such as line breaks and paragraph structure
4. For technical terms, provide accurate translations
5. Only output the translated text, without any explanations or additional content"""

        if context:
            prompt += f"\n\nContext: {context}"

        return prompt

    def _call_api(
        self,
        system_prompt: str,
        text: str,
        max_retries: int = 3,
    ) -> str:
        """调用OpenAI API
        
        Args:
            system_prompt: 系统提示词
            text: 要翻译的文本
            max_retries: 最大重试次数
            
        Returns:
            翻译结果
        """
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                    temperature=0.3,  # 较低温度保证翻译一致性
                )
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"翻译API调用失败: {e}") from e

    def _merge_short_paragraphs(
        self,
        paragraphs: List[str],
        max_chars: int = 2000,
    ) -> List[str]:
        """合并短段落以减少API调用
        
        Args:
            paragraphs: 段落列表
            max_chars: 每个块的最大字符数
            
        Returns:
            合并后的文本块列表
        """
        chunks = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            para_length = len(para)
            
            if current_length + para_length > max_chars and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length + 2  # +2 for "\n\n"

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

