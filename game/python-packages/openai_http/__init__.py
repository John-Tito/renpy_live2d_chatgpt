__version__ = "1.0.0"

# Import required libraries
import requests
import json
import logging
import threading
import re
from queue import Queue
import re
from itertools import zip_longest

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="client.log",
    filemode="a",
)

class MessageHistory:
    def __init__(self, base_prompt, max_length=5):
        self.history = [base_prompt]
        self.max_length = max_length

    def append(self, message):
        """追加消息并保持历史记录长度不超过最大值"""
        self.history.append(message)
        if len(self.history) > self.max_length:
            self.history = [self.history[0]] + self.history[-(self.max_length - 1):]

    def copy(self):
        """返回历史记录的副本"""
        return self.history.copy()

    def clear(self):
        """清除历史记录，保留初始提示"""
        self.history = [self.history[0]]

class Client:
    def __init__(self, api_key, api_url="https://api.openai.com/v1/chat/completions",
                 base_prompt="你是一个人工智能助手", model="gpt-3.5-turbo", default_params=None):
        """
        初始化客户端。
        :param api_key: OpenAI API 密钥
        :param api_url: API URL，默认为 OpenAI 的聊天补全 API
        :param base_prompt: 初始系统提示
        :param model: 使用的模型，默认为 gpt-3.5-turbo
        :param default_params: 默认参数，默认为空字典
        """
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.default_params = default_params if default_params is not None else {}
        self.history = MessageHistory({"role": "system", "content": base_prompt}, 10)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        })
        self.adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=100)
        self.session.mount('https://', self.adapter)
        self.logger = logging.getLogger(__name__)  # 创建日志记录器
        self.is_running = False

    def close(self):
        """关闭会话并记录日志"""
        self.session.close()
        self.logger.info("Session closed")

    def start_fetching(self, prompt, reply_queue, timeout=40):
        """
        启动后台线程以获取ChatAPI的响应。
        :param prompt: 用户输入的提示
        :param reply_queue: 用于接收API响应的队列
        :param timeout: 请求超时时间，默认为40秒
        """
        if self.is_running:
            raise RuntimeError("ChatAPIHandler is already running.")

        self.is_running = True
        self.buffer = ""  # 清空缓冲区
        thread = threading.Thread(target=self._fetch_response, args=(prompt, reply_queue, timeout), daemon=True)
        thread.start()

    def stop_fetching(self):
        """停止后台线程"""
        self.is_running = False

    def _fetch_response(self, text, reply_queue, timeout=40):
        """
        内部方法：从ChatAPI获取响应并处理流数据。
        :param text: 用户输入的文本
        :param reply_queue: 用于接收API响应的队列
        :param timeout: 请求超时时间，默认为40秒
        """
        try:
            request_data = self._prepare_request_data(text)
            response = self._send_request(request_data, timeout)
            self._process_stream(response, reply_queue)
        except requests.exceptions.RequestException as e:
            self.logger.error("Error occurred while fetching response: %s", str(e))
        finally:
            reply_queue.put("")
            self.is_running = False  # 确保 is_running 被重置

    def _prepare_request_data(self, text):
        """
        准备请求数据。
        :param text: 用户输入的文本
        :return: 请求数据字典
        """
        temp_history = self.history.copy()
        temp_history.append({"role": "user", "content": text})
        request_data = {
            "model": self.model,
            "messages": temp_history,
            "stream": True,
            **self.default_params
        }
        self.logger.debug("Request Data: %s", request_data)
        return request_data

    def _send_request(self, request_data, timeout):
        """
        发送HTTP请求。
        :param request_data: 请求数据字典
        :param timeout: 请求超时时间
        :return: 响应对象
        """
        response = self.session.post(
            self.api_url,
            data=json.dumps(request_data),
            timeout=timeout,
            stream=True
        )
        response.raise_for_status()  # 检查HTTP错误
        return response

    def _process_stream(self, response, reply_queue):
        """
        处理流式响应。
        :param response: 响应对象
        :param reply_queue: 用于接收API响应的队列
        """
        for line in response.iter_lines():
            if not self.is_running:
                break

            if not line:
                continue

            line_str = line.decode('utf-8')
            if not line_str.startswith("data: "):
                continue

            event_data = line_str[6:]
            if event_data == "[DONE]":
                break

            chunk = self._parse_chunk(event_data)
            if chunk:
                content = chunk["choices"][0].get("delta", {}).get("content", "")
                if content:
                    self.buffer += content
                    self._handle_buffer(reply_queue)

        if self.buffer:
            reply_queue.put(self.buffer.strip())

    def _parse_chunk(self, event_data):
        """
        解析JSON数据块。
        :param event_data: JSON 数据字符串
        :return: 解析后的数据字典，或None如果解析失败
        """
        try:
            return json.loads(event_data)
        except json.JSONDecodeError:
            return None

    def _handle_buffer(self, reply_queue):
        """
        处理缓冲区中的句子。
        :param reply_queue: 用于接收API响应的队列
        """
        # 检查是否有完整的句子（假设句子以常见标点符号结束）
        if self._has_complete_sentence():
            sentences = self._split_sentences()
            for sentence in sentences[:-1]:  # 处理所有完整的句子
                reply_queue.put(sentence.strip())
            self.buffer = sentences[-1]  # 保留不完整的句子

    def _has_complete_sentence(self):
        """
        检查缓冲区中是否有完整的句子。
        :return: 如果有完整的句子返回 True，否则返回 False
        """
        return bool(re.search(r'[.!?。！？]', self.buffer))

    def _split_sentences(self):
        """
        使用正则表达式分割缓冲区中的句子。
        :return: 分割后的句子列表
        """
        # 匹配句号、问号、感叹号（包括中文和英文），并保留这些符号
        # 同时处理连续的标点符号
        sentences = re.split(r'([.!?。！？]+)', self.buffer)
        # 合并分割符号与句子，并去除空字符串
        sentences = ["".join(pair).strip() for pair in zip_longest(sentences[::2], sentences[1::2], fillvalue="")]
        # 过滤掉空字符串
        sentences = [sentence for sentence in sentences if sentence]
        # 确保最后一个元素是不完整的句子
        if sentences and not re.search(r'[.!?。！？]$', sentences[-1]):
            incomplete_sentence = sentences.pop()
            sentences.append(incomplete_sentence)
        return sentences

    def _clean_sentences(self, sentences):
        """
        清理分割后的句子，去除多余的空白字符和其他不必要的字符。
        :param sentences: 分割后的句子列表
        :return: 清理后的句子列表
        """
        cleaned_sentences = []
        for sentence in sentences:
            # 去除句子开头和结尾的多余空白字符
            cleaned_sentence = sentence.strip()
            # 处理引号和其他特殊字符
            cleaned_sentence = re.sub(r'\s+', ' ', cleaned_sentence)  # 替换多个空白字符为一个空格
            cleaned_sentence = re.sub(r'^["\u201C\u2018]+|["\u201D\u2019]+$', '', cleaned_sentence)  # 去除引号
            cleaned_sentences.append(cleaned_sentence)
        return cleaned_sentences