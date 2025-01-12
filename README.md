# Amadeus - Ren'Py Visual Novel

## 项目概述
这是一个在Ren'Py引擎使用live2d和chatgpt(deepseek chat)的测试demo.

## 项目结构
```
game/
├── gui/ - 游戏界面资源
├── images/ - 背景图片
├── live2d/ - Live2D角色模型和动画
├── saves/ - 游戏存档
├── tl/ - 翻译文件
├── gui.rpy - 界面设置
├── options.rpy - 游戏配置
├── screens.rpy - 屏幕定义
├── get_label.rpy - 游戏脚本
└── script.rpy - 主游戏脚本
```

## 运行游戏
1. 确保已安装 Ren'Py SDK
2. 确保已安装 CubismSdkForNative
3. 在环境变量中配置 API KEY : "OPENAI_API_KEY"或自行修改相关配置

```python
    # game\script.rpy
    ai_client = Client(
        model="deepseek-chat",
        api_url="https://api.deepseek.com/chat/completions",
        api_key=os.getenv("OPENAI_API_KEY"),
        base_prompt = base_prompt
    )
```

4. 在项目根目录运行：
   ```bash
   renpy game
   ```
5. 游戏将启动并显示主菜单

## 依赖
- Ren'Py-8.3.4
- CubismSdkForNative-5-r.2

## 素材声明
本项目中使用的所有素材（包括但不限于图片、音频、字体等）仅用于学习目的。如果您是素材的版权所有者并认为这些素材的使用侵犯了您的权利，请联系我进行删除。

## 许可证
本项目采用MIT许可证。详情请查看LICENSE文件。
