init:
    define config.gl2 = True

define CRS = Character("Makise Kurisu")

# live2d 模型路径
define live2d_path = "live2d/amadeusV1"
# 获取角色的动作和表情
define cp = CharacterPreprocessor(live2d_path)

# 加载live2d模型
image crs_close = Live2D(live2d_path, loop=False, base=.6)
image crs_far = Live2D(live2d_path, base=.9)

# 默认动作和表情
default exp_s = ""
default motion_s = ""

init python:
    import threading
    import io
    import os
    import tempfile
    from queue import Queue

    import ai_config
    from VisualNovelAIAssistant import VisualNovelAIAssistant

    # 全局消息队列
    reply = ""
    is_answering = False

    # 创建一个回复队列
    reply_queue = Queue()

    # 初始化客户端
    ai_client = VisualNovelAIAssistant(
        api_url=ai_config.llm_api_url,
        api_key=ai_config.llm_api_key,
        model=ai_config.llm_modle,
        base_prompt = ai_config.llm_base_prompt,
        reply_queue=reply_queue,
    )

    ai_client.use_tts = True

    # 加载历史记录
    ai_client.load_history()

    def play_audio_from_bytes(audio_bytes):

        # 指定临时文件目录
        TEMP_DIR = os.path.join(config.basedir, "voice")  # 在游戏根目录下创建 temp_audio 文件夹

        # 确保临时文件目录存在
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(dir=TEMP_DIR, delete=False, suffix=".wav") as temp_file:
            temp_file.write(audio_bytes)
            temp_file_path = temp_file.name

        # 返回 voice/***.wav 格式的路径
        return ("voice/" + os.path.basename(temp_file_path))

    # 定义退出回调函数
    def on_quit():
        # 在这里添加退出时的逻辑
        ai_client.save_history()
        renpy.quit()

    # 将回调函数绑定到 config.quit_action
    config.quit_action = on_quit

# 游戏开始
label start:

    scene bg

    # 初始问候
    show crs_close mtn_01
    pause 1.0

    CRS "你好"

    while True:

        label get_user_input:
            # 获取用户输入
            $ user_input = renpy.input("你:", length=100)

            # 检查空输入
            if user_input.strip() == "":
                jump get_user_input

        # 开始异步处理
        $ ai_client.start_fetching(user_input)

        $ reply = f"正在思考"
        $ is_answering = True
        CRS "[reply]"

        # 显示回复
        while is_answering or not reply_queue.empty():

            if not reply_queue.empty():
                $ reply_package = reply_queue.get()
                if reply_package and  reply_package['jp'] and reply_package['cn']:

                    $ reply = reply_package['cn']

                    if reply_package['audio']:
                        $ audio_file = play_audio_from_bytes(reply_package['audio'])
                        $ print("播放音频：", audio_file)
                        play sound audio_file

                    CRS "[reply]"

                else:
                    $ is_answering = False

            else:
                pause 0.5

    # 游戏结束
    return