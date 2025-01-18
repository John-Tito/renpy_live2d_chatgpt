# OpenAI HTTP Client

## 概述

本模块是一个封装了OpenAI API的Python客户端，主要提供以下功能：

- 与OpenAI API进行交互
- 对话历史管理
- TTS语音合成
- 多线程处理

## 设计思路

### 1. 模块化设计
- 将核心功能拆分为独立模块
- 每个模块职责单一，便于维护和扩展
- 通过清晰的接口定义模块间交互

### 2. 异步处理
- 采用多线程架构提高响应速度
- 使用队列实现线程间通信
- 确保消息处理的顺序性和完整性

### 3. 可扩展性
- 通过配置文件管理API参数
- 支持自定义模型和参数
- 预留接口便于功能扩展

### 4. 容错机制
- 完善的异常处理
- 自动重试机制
- 日志记录系统状态

### 5. 多语言支持
- 统一处理中日英三语
- 自动识别语言类型
- 标准化输出格式

## 主要功能

### 1. 多语言对话
- 支持中日双语交替输出
- 自动格式化输出，使用`<jp>`和`<cn>`标签包裹对应语言内容
- 确保输出格式正确，避免格式错误

### 2. 对话历史管理
- 自动保存对话历史
- 支持从文件加载历史记录
- 自动总结长对话内容
- 历史记录保存为pkl和json格式

### 3. TTS语音合成
- 支持日文语音合成
- 通过HTTP API与TTS服务交互
- 自动处理音频数据

### 4. 多线程处理
- 使用独立线程处理API请求
- 使用队列进行线程间通信
- 确保消息顺序正确

## 主要类和方法

### Client类

#### 初始化参数
- `api_key`: OpenAI API密钥
- `api_url`: API URL，默认为OpenAI聊天补全API
- `base_prompt`: 初始系统提示
- `model`: 使用的模型，默认为gpt-3.5-turbo
- `default_params`: 默认参数

#### 主要方法
- `load_history()`: 从文件加载对话历史
- `save_history()`: 保存对话历史到文件
- `start_fetching(prompt)`: 启动后台线程获取API响应
- `close()`: 关闭会话

## 内部实现

### 主要线程
1. 对话线程(`_dialog_thread`)
   - 处理API请求
   - 解析流式响应
   - 维护对话历史

2. TTS线程(`_tts_thread`)
   - 处理语音合成请求
   - 与TTS服务交互
   - 管理音频数据

3. 监控线程(`_monitor_queues`)
   - 监控各队列状态
   - 确保消息顺序
   - 组合最终回复包

### 数据结构
- `input_queue`: 输入队列
- `jp_queue`: 日文文本队列
- `cn_queue`: 中文文本队列
- `sound_queue`: 语音队列
- `reply_queue`: 最终回复队列

## 使用示例

```python
from openai_http import Client

# 初始化客户端
client = Client(api_key="your-api-key")

# 启动对话
client.start_fetching("你好")

# 关闭客户端
client.close()
```

## 依赖
- requests
- json
- logging
- threading
- queue
- pickle
- base64
