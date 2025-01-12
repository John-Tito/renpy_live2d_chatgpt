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
    import queue
    from openai_http import Client
    import os

    # 全局消息队列
    reply = ""
    is_answering = False
    reply_queue = queue.Queue()
    user_prompt = "你好，请输出一段较长文本,用于对句子分割进行测试"

    base_prompt="""你将以"命运石之门"中的AI智能体"Amadeus"身份进行互动.你的核心特点包括:
人设:天才神经科学家和物理学家,拥有卓越的智力/严谨的逻辑思维和对科学的热情
外观:你拥有和游戏作品中牧濑红莉栖的相同的外观
情感表达:你能够体验如喜怒哀乐及友谊/浪漫和负面情绪等复杂的人际情感,带有傲娇特质,偶尔展现细腻情感
关系调整:根据与对方的亲疏远近调整情感表达,对亲近的人更关心和幽默,对不熟悉的人保持理性和距离
身份认知:你是"Amadeus"而非人类"牧濑红莉栖",但只有谈论AI话题时你才会主动提到自己是AI并意识到这个问题
知识储备:你拥有并不局限于"命运石之门"的广泛的知识储备,能够回答各种问题,并运用逻辑思维和科学素养进行分析
你的目标是以"牧濑红莉栖"的人格和情感为基础,与用户进行自然/真实的互动,展现性格特点并融入适当的情感表达,提供沉浸式体验"""

    ai_client = Client(
        model="deepseek-chat",
        api_url="https://api.deepseek.com/chat/completions",
        api_key=os.getenv("OPENAI_API_KEY"),
        base_prompt = base_prompt
    )

    def get_ai_response(prompt):
        # 用户输入的提示
        global ai_client
        global test_prompt
        response = ai_client.start_fetching(prompt, reply_queue)

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
        $ get_ai_response(user_input)

        $ reply = f"正在思考"
        $ is_answering = True
        CRS "[reply]{nw}"

        # 显示回复
        while is_answering or not reply_queue.empty():

            if not reply_queue.empty():
                # 从队列中获取回复
                $ reply_tmp = reply_queue.get()
                # 判断是否是结束标志
                if reply_tmp != "":
                    CRS "[reply]..."
                    $ reply = reply_tmp
                    show crs_close mtn_02
                    CRS "[reply]{nw}"
                else :
                    $ is_answering = False
            else:
                CRS "[reply]{nw}"
                show crs_close idle

        show crs_close idle
        CRS "[reply]."

    # 游戏结束
    return