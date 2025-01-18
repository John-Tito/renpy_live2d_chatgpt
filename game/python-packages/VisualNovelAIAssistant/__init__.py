__version__ = "1.0.0"

# Import required libraries
import requests
import json
import logging
import threading
import time
import pickle
import re
import base64
import io
import os
import asyncio
from queue import Queue
from itertools import zip_longest

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="VisualNovelAIAssistant.log",
    filemode="w",
    encoding="utf-8"
)

class VisualNovelAIAssistant:
    def __init__(self, api_key, reply_queue ,api_url="https://api.openai.com/v1/chat/completions",
                 base_prompt="你是一个人工智能助手", model="gpt-3.5-turbo", default_params=None):
        """
        初始化客户端
        :param api_key: OpenAI API 密钥
        :param api_url: API URL，默认为 OpenAI 的聊天补全 API
        :param base_prompt: 初始系统提示
        :param model: 使用的模型，默认为 gpt-3.5-turbo
        :param default_params: 默认参数，默认为空字典
        """

        # LLM 配置
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.base_prompt =[
            {
                "role": "system",
                "content": base_prompt,
            },
            {
                "role": "system",
                "content":
"""格式化输出要求,请务必遵守该要求:
-用日文清晰简洁地回答问题,确保日文回复使用<jp>sentence</jp>标签包裹
-用中文清晰简洁地回答同样的问题,确保中文回复使用<cn>sentence</cn>标签包裹
-确保意思完整的同时将长句拆分成较短的部分
-确保交替输出两种语言的回复,每次回答一句日文回复(不是整个回复)后紧跟着输出对应的中文回复
-确保标签使用英文字符,确保标签闭合,整个回复不要使用无意义的空白字符以避免格式错误
-当句子中出现其他语言元素（如英文或符号）时，直接包含在相应的标签内，确保不会影响格式的正确性。
举例,对于一段完整的回复,应该是如下格式:
用户输入:你是谁?
回复:<jp>おかしいな、何をしているの？</jp>
<cn>真奇怪，你在做什么？</cn>
<jp>私は牧瀬紅莉栖だよ。</jp>
<cn>我是牧濑红莉栖啊。</cn>
"""
            }
        ]

        self.summary_prompt = {
            "role": "user",
            "content": "总结之前的对话内容,保留核心信息同时尽可能简洁,总结应带有明显的角色思维情感特征"
        }
        self.default_params = default_params if default_params is not None else {}
        self.summarize_length = 8
        self.use_tts = False

        # TTS 配置
        self.tts_api_url = "http://127.0.0.1:8000/synthesize"

        # 消息历史
        self.history    = []
        self.history_cn = []
        self.history_jp = []

        # 日志和状态
        self.logger = logging.getLogger(__name__)
        self.is_running = True

        self.input_queue = Queue()
        self.jp_queue = Queue()    # 日文文本队列
        self.cn_queue = Queue()    # 中文文本队列
        self.jp_queue_tts = Queue()  # 待处理的日文文本队列
        self.sound_queue = Queue() # 日文语音队列
        self.reply_queue = reply_queue # 回复队列

        self.sequence_lock = threading.Lock()
        self.sequence_counter = 0

        # 启动对话线程
        self.dialog_thread = threading.Thread(target=self._dialog_thread, daemon=True)
        self.dialog_thread.start()

        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_queues, daemon=True)
        self.monitor_thread.start()

        # 启动TTS线程
        self.tts_thread = threading.Thread(target=self._tts_thread, daemon=True)
        self.tts_thread.start()

    def load_history(self):
        """
        从文件中加载消息历史
        """
        try:
            # 加载消息历史
            if os.path.exists("history/history.pkl"):
                with open("history/history.pkl", "rb") as f:
                    self.history = pickle.load(f)
            else:
                self.logger.info("history/history.pkl does not exist")

            # 加载中文消息历史
            if os.path.exists("history/history_cn.pkl"):
                with open("history/history_cn.pkl", "rb") as f:
                    self.history_cn = pickle.load(f)
            else:
                self.logger.info("history/history_cn.pkl does not exist")

            # 加载日文消息历史
            if os.path.exists("history/history_jp.pkl"):
                with open("history/history_jp.pkl", "rb") as f:
                    self.history_jp = pickle.load(f)
            else:
                self.logger.info("history/history_jp.pkl does not exist")
        except Exception as e:
            self.logger.error(f"Error loading history: {e}")

    def save_history(self):
        """
        保存消息历史到文件
        """

        try :
            # 检测文件夹是否存在
            if not os.path.exists("history"):
                os.makedirs("history")

            with open("history/history.pkl", "wb") as f:
                pickle.dump(self.history, f)

            with open("history/history_cn.pkl", "wb") as f:
                pickle.dump(self.history_cn, f)

            with open("history/history_jp.pkl", "wb") as f:
                pickle.dump(self.history_jp, f)

            with open("history/history.json", 'w', encoding='utf-8') as file:
                json.dump(self.history, file, ensure_ascii=False, indent=4)

            with open("history/history_cn.json", 'w', encoding='utf-8') as file:
                json.dump(self.history_cn, file, ensure_ascii=False, indent=4)

            with open("history/history_jp.json", 'w', encoding='utf-8') as file:
                json.dump(self.history_jp, file, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.error(f"Error loading history: {e}")

    def close(self):
        """关闭会话并记录日志"""
        self.logger.info("Session closed")

    def start_fetching(self, prompt):
        """
        启动后台线程以获取ChatAPI的响应
        :param prompt: 用户输入的提示
        """
        self.input_queue.put(prompt)

    def _summarize(self):
        self.logger.info("history len: " + str(len(self.history)))
        if len(self.history) > self.summarize_length:
            self.logger.info("Start summarizing")
            # 复制历史并添加总结提示
            temp_history = self.history.copy()
            temp_history.append(self.summary_prompt)
            # 发送总结请求
            summary_content = self._get_chat_response_sync(messages = temp_history)
            # 清空历史并添加总结
            if summary_content:
                self.logger.info(f"Summarize success")
                self.history = [{"role": "assistant", "content": summary_content}]
            else:
                self.logger.info(f"Summarize failed")

    def _get_chat_response_sync(self, messages, timeout=40):
        """使用同步的HTTP请求获取AI响应"""
        content = ""  # 默认返回空字符串，避免调用方处理 None
        try:

            # 合并默认参数，优先使用 self.default_params 中的值
            params = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 8192,  # 默认值
                "presence_penalty": 1.0,
                **self.default_params  # 覆盖默认值
            }

            # 发送请求
            response = requests.request(
                "POST",
                self.api_url,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    "Authorization": f"Bearer {self.api_key}"
                },
                json=params,
                timeout=timeout
            )

            # 检查 HTTP 错误
            response.raise_for_status()

            # 解析响应内容
            response_data = response.json()
            if "choices" in response_data and len(response_data["choices"]) > 0:
                content = response_data["choices"][0]["message"]["content"]
                self.logger.info("Received response: %s", content)
            else:
                self.logger.error("Unexpected response format: %s", response_data)

        except requests.exceptions.RequestException as e:
            # 网络或 HTTP 错误
            self.logger.error("Request failed: %s", str(e))
        except ValueError as e:
            # JSON 解析错误
            self.logger.error("Failed to parse response JSON: %s", str(e))
        except KeyError as e:
            # 响应格式不符合预期
            self.logger.error("Unexpected response structure: %s", str(e))
        except Exception as e:
            # 其他未知错误
            self.logger.error("Unexpected error: %s", str(e))
        finally:
            return content

    def _dialog_thread(self, timeout=40):
        """
        内部方法：从ChatAPI获取响应并处理流数据
        :param timeout: 请求超时时间，默认为40秒
        """

        # HTTP 长链接
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        })

        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=100)
        session.mount('https://', adapter)

        while self.is_running:

            if not self.input_queue.empty():

                text = self.input_queue.get()

                try:
                    # 创建临时历史记录
                    temp_history = self.history.copy()
                    temp_history.extend(self.base_prompt)
                    temp_history.append({"role": "user", "content": text})

                    # 创建请求数据
                    request_data = {
                        "model": self.model,
                        "messages": temp_history,
                        "stream": True,
                        "max_tokens" : 8192,
                        "frequency_penalty":2.0,
                        "temperature":1.3,
                        "presence_penalty": 1.0,
                        **self.default_params
                    }

                    self.logger.info("Sending request to LLM API, Request data: %s", request_data)

                    response = session.post(
                        self.api_url,
                        data=json.dumps(request_data),
                        timeout=timeout,
                        stream=True
                    )

                    response.raise_for_status()  # 检查HTTP错误

                    self.logger.info( "Response received from LLM API")

                    self._process_stream( text,response )

                except requests.exceptions.RequestException as e:
                    self.logger.error("Error occurred while fetching response: %s", str(e))
            else :
                time.sleep(0.1)

    def _process_stream(self, text , response ):

        final_response = "" # 完整回复
        final_response_cn = "" # 中文回复
        final_response_jp = "" # 日文回复
        response_buffer = "" # 字符串处理缓冲区

        response_phase = 0

        seq = self._get_sequence_number()

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

            chunk = json.loads(event_data)
            if chunk:
                content = chunk["choices"][0].get("delta", {}).get("content", "")
                if content:

                    final_response += content
                    response_buffer += content

                    jp_start = response_buffer.find('<jp>')
                    if jp_start != -1:
                        jp_end = response_buffer.find('</jp>', jp_start)
                        if jp_end != -1:
                            # 检测到一句完整的日文文本
                            jp_content = response_buffer[jp_start+4:jp_end]
                            final_response_jp += jp_content
                            self.jp_queue.put({'seq': seq, 'content': jp_content})
                            self.jp_queue_tts.put({'seq': seq, 'content': jp_content})
                            response_buffer = response_buffer[jp_end+5:]
                            response_phase = 1

                    if response_phase == 1:
                        cn_start = response_buffer.find('<cn>')
                        if cn_start != -1:
                            cn_end = response_buffer.find('</cn>', cn_start)
                            if cn_end != -1:
                                # 检测到一句完整的中文文本
                                cn_content = response_buffer[cn_start+4:cn_end]
                                final_response_cn += cn_content
                                self.cn_queue.put({'seq': seq, 'content': cn_content})
                                # 从缓冲区中移除已处理的内容
                                response_buffer = response_buffer[cn_end+5:]
                                # 申请新的序列号
                                seq = self._get_sequence_number()
                                response_phase == 0

        if final_response:
            self.logger.info("Received data: %s", final_response)

        # 全部接收完成后将完整的中文回复和日文回复分别放入对应的消息队列
        if final_response_cn and final_response_jp:
            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": final_response_cn})
            self.history_cn.append({"role": "user", "content": text})
            self.history_cn.append({"role": "assistant", "content": final_response_cn})
            self.history_jp.append({"role": "user", "content": text})
            self.history_jp.append({"role": "assistant", "content": final_response_jp})

        self.jp_queue_tts.put({'seq': seq, 'content': None})
        self.jp_queue.put({'seq': seq, 'content': None})
        self.cn_queue.put({'seq': seq, 'content': None})
        seq = self._get_sequence_number()
        self._summarize()

    def _tts_thread(self):

        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json"
        })
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=100)
        session.mount('http://', adapter)

        while self.is_running:
            if not self.jp_queue_tts.empty():

                response_content = None

                tts_text_seq = self.jp_queue_tts.queue[0]['seq']
                tts_text = self.jp_queue_tts.queue[0]['content']
                self.jp_queue_tts.get()

                if tts_text and self.use_tts:

                    try:
                        self.logger.info("Sending request to the tts API...")

                        request_data = {"text": tts_text}

                        response = session.post(
                            self.tts_api_url,
                            data=json.dumps(request_data)
                        )

                        response.raise_for_status()  # 检查请求是否成功
                        result = response.json()

                        self.logger.info("Response received.")

                        # 检查返回的音频数据
                        if "audio" in result:
                            self.logger.info("Audio data received as Base64.")

                            # 解码 Base64 音频数据
                            audio_base64 = result["audio"]
                            audio_bytes = base64.b64decode(audio_base64)

                            self.logger.info("Audio decoded.")

                            # 使用 soundfile 直接从内存中读取音频数据
                            response_content = audio_bytes
                        else:
                            self.logger.info("Unexpected response format. No audio data found.")
                    except requests.exceptions.RequestException as e:
                        self.logger.info(f"Request failed: {e}")
                    except Exception as e:
                        self.logger.info(f"An error occurred: {e}")

                self.sound_queue.put({"seq": tts_text_seq, "content" : response_content})
                self.logger.info("TTS Response processed.")

            else :
                time.sleep(0.1)

    def _get_sequence_number(self):
        with self.sequence_lock:
            seq = self.sequence_counter
            self.sequence_counter += 1
            return seq

    def _monitor_queues(self):
        while self.is_running:
            # 检查是否有序列号在所有队列中都有数据
            if not self.jp_queue.empty() and not self.cn_queue.empty() and not self.sound_queue.empty():
                # 查看队列头部的序列号，但不取出
                jp_seq = self.jp_queue.queue[0]['seq']
                cn_seq = self.cn_queue.queue[0]['seq']
                sound_seq = self.sound_queue.queue[0]['seq']

                # 找到三个队列中最大的序列号
                max_seq = max(jp_seq, cn_seq, sound_seq)

                # 丢弃所有队列中小于最大序列号的数据
                while not self.jp_queue.empty() and self.jp_queue.queue[0]['seq'] < max_seq:
                    self.jp_queue.get()  # 丢弃不匹配的数据
                while not self.cn_queue.empty() and self.cn_queue.queue[0]['seq'] < max_seq:
                    self.cn_queue.get()  # 丢弃不匹配的数据
                while not self.sound_queue.empty() and self.sound_queue.queue[0]['seq'] < max_seq:
                    self.sound_queue.get()  # 丢弃不匹配的数据

                # 再次检查是否有数据
                if not self.jp_queue.empty() and not self.cn_queue.empty() and not self.sound_queue.empty():
                    # 取出各队列中的数据
                    jp_item = self.jp_queue.get()
                    cn_item = self.cn_queue.get()
                    sound_item = self.sound_queue.get()

                    # 检查序列号是否匹配
                    if jp_item['seq'] == cn_item['seq'] == sound_item['seq']:
                        seq = jp_item['seq']
                        # 组合成回复包
                        reply_package = {
                            'jp': jp_item['content'],
                            'cn': cn_item['content'],
                            'audio': sound_item['content']
                        }
                        self.reply_queue.put(reply_package)
                    else:
                        # 如果仍然不匹配，丢弃这些数据（理论上不会发生）
                        pass
            else:
                # 队列为空时，休眠一段时间
                time.sleep(0.1)