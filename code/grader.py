import base64
import gradio as gr
from openai import OpenAI
import os
import datetime
import json
import pandas as pd
from pathlib import Path
import re
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from typing import Generator

# --- 日志配置 ---
LOG_FILE = "app.log"
logging.basicConfig(
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=5)],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def log_event(event_type: str, status: str, details: str = ""):
    """记录系统事件"""
    logger.info(f"[{event_type}] {status} | {details}")

# --- 加载环境变量 ---
load_dotenv(override=True)
TEXTS_DIR = "texts"
RATES_DIR = "rates"
HISTORY_PATH = "history.json"
os.makedirs(TEXTS_DIR, exist_ok=True)
os.makedirs(RATES_DIR, exist_ok=True)

# --- 配置参数 ---
class Config:
    API_BASE_URL = os.getenv("MODELSCOPE_API_ENDPOINT", "https://api-inference.modelscope.cn/v1/")
    API_KEY = os.getenv("MODELSCOPE_API_KEY")
    EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct") 
    RATING_MODEL = os.getenv("RATING_MODEL", "Qwen/Qwen2.5-32B-Instruct") 
    MAX_FILE_SIZE_MB = 5
    ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png"]

config = Config()

# --- 历史记录功能 ---
def load_history() -> list:
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log_event("SYSTEM", "历史记录加载失败", str(e))
        return []

def save_history(history: list) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# --- Helper Functions ---
def sanitize_filename(title: str) -> str:
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title.strip())
    return sanitized[:50]

def safe_save(content: str, directory: str, filename: str) -> str:
    safe_dir = Path(directory).resolve()
    safe_dir.mkdir(exist_ok=True)
    safe_name = sanitize_filename(filename)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = safe_dir / f"{safe_name}_{timestamp}.txt"
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(save_path)

def validate_image_files(files: list[str]) -> None:
    if not files:
        raise ValueError("未上传任何图片")
    for file_path in files:
        file = Path(file_path)
        if not file.exists():
            raise ValueError(f"文件不存在: {file_path}")
        if file.suffix.lower() not in config.ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {file.suffix}")
        if file.stat().st_size > config.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"文件过大: {file.name} ({file.stat().st_size//1024//1024}MB)")

def encode_image_to_base64(image_path: str) -> str:
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        log_event("ERROR", "图片编码失败", str(e))
        raise

# --- 核心处理逻辑 ---
def stream_extract_text(image_paths: list[str]) -> Generator[str, None, str]:
    client = OpenAI(base_url=config.API_BASE_URL, api_key=config.API_KEY)
    
    messages = [{
        "type": "text",
        "text": "忽略红色的批改文本和其他乱涂乱画的笔迹，提取出图片中作文的文本内容，包括作文题目和作文正文。"
                "你的回复的第一行是作文题目，接下来是作文正文，不要包含其他任何多余内容。"
                "对于文中的错别字，你无需修正，同时，输出文本的段落结构需要与作文中的段落结构保持一致"
    }]

    for path in image_paths:
        base64_image = encode_image_to_base64(path)
        messages.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
        })

    response = client.chat.completions.create(
        model=config.EXTRACTION_MODEL,
        messages=[{"role": "user", "content": messages}],
        stream=True
    )

    full_text = ""
    for chunk in response:
        if chunk.choices[0].delta.content:
            chunk_text = chunk.choices[0].delta.content
            full_text += chunk_text
            yield full_text
    return full_text

def stream_rate_text(content: str) -> Generator[str, None, str]:
    client = OpenAI(base_url=config.API_BASE_URL, api_key=config.API_KEY)
    
    try:
        prompt_path = Path("prompt/prompt.txt")
        if not prompt_path.exists():
            raise FileNotFoundError("评分模板文件不存在")
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        response = client.chat.completions.create(
            model=config.RATING_MODEL,
            messages=[
                {"role": "system", "content": "你是一位专业的语文老师，需要根据评分标准对作文进行详细批改"},
                {"role": "user", "content": f"{prompt_template}\n作文内容如下：{content}"}
            ],
            stream=True,
            temperature=1
        )

        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                chunk_text = chunk.choices[0].delta.content
                full_response += chunk_text
                yield full_response
        return full_response

    except Exception as e:
        log_event("ERROR", "评分失败", str(e))
        raise

# --- Gradio界面 ---
def create_interface():
    with gr.Blocks(
        theme=gr.themes.Soft(), 
        title="作文智能批改系统",
        css="""
        .drag-area {
            border: 2px dashed #666;
            border-radius: 10px;
            padding: 20px;
            transition: all 0.3s;
            min-height: 500px;
            position: relative;
        }
        .result-area {
            overflow: none;
            border: 2px dashed #666;
            border-radius: 10px;
            padding: 20px 20px 0 20px;
        }
        .drag-area.dragover {
            border-color: #2196F3;
            background: #f5fbff;
        }
        #upload-btn {
        }
        .fixed-height {
            height: 750px;
            overflow: auto;
            box-sizing: border-box;
            border: 3px solid #e0e0e0;
            padding: 10px 10px 0 10px;
            border-radius: 15px;
            font-size: 25px;
        }
        .fixed-height::-webkit-scrollbar {
            width: 2px;
        }
        .fixed-height::-webkit-scrollbar-thumb {
            background: #888;
            border-radius: 4px;
        }
        """
    ) as demo:
        history_state = gr.State(value=load_history())
        uploaded_files = gr.State([])

        # 界面布局
        gr.Markdown("<center><h1>📚 智能作文批改系统</h1></center>")
        gr.Markdown("<center><h3>上传作文图片，自动提取文字并生成批改建议</h3></center>")
# --- Gradio界面 ---
def create_interface():
    with gr.Blocks(
        theme=gr.themes.Soft(),
        title="作文智能批改系统",
        css="""
        .drag-area {
            border: 2px dashed #666;
            border-radius: 10px;
            padding: 20px;
            transition: all 0.3s;
            min-height: 500px;
            position: relative;
        }
        .result-area {
            overflow: visible; /* 移除外侧滚动条 */
            border: 2px dashed #666;
            border-radius: 10px;
            padding: 10px 10px 0 10px;
            display: flex; /* 使用 flex 布局 */
            justify-content: center; /* 水平居中 */
        }
        .drag-area.dragover {
            border-color: #2196F3;
            background: #f5fbff;
        }
        #upload-btn {
        }
        .fixed-height {
            height: 520px;
            overflow: auto; /* 内部滚动条 */
            box-sizing: border-box;
            border: 3px solid #e0e0e0;
            padding: 10px 10px 0 10px;
            border-radius: 15px;
            font-size: 25px;
            width: 100%; /* 设置宽度为 100% */
        }
        """
    ) as demo:
        history_state = gr.State(value=load_history())
        uploaded_files = gr.State([])

        # 界面布局
        gr.Markdown("<center><h1>📚 智能作文批改系统</h1></center>")
        gr.Markdown("<center><h3>上传作文图片，自动提取文字并生成批改建议</h3></center>")

         # 界面布局改进
        with gr.Row():
            with gr.Column(scale=4):
                # 改进拖拽区域
                with gr.Column(elem_classes="drag-area"):
                    image_gallery = gr.Gallery(
                        label="已上传图片",  # 添加拖拽提示
                        columns=3,
                        height=500,
                        object_fit="contain",
                        preview=True,
                    )
                    with gr.Row():
                        upload_btn = gr.UploadButton(
                            "上传作文图片",
                            file_types=config.ALLOWED_EXTENSIONS,
                            file_count="multiple",
                            variant="primary",
                            elem_id="upload-btn"
                        )
                        start_btn = gr.Button("开始批改", variant="stop")
                next_btn = gr.Button("批改下一篇", variant="secondary")

            with gr.Column(scale=6, elem_classes="result-area"):
                process_status = gr.Markdown("**当前状态**: 等待上传图片")
                
                # 固定高度内容区域
                with gr.Tabs():
                    with gr.TabItem("提取内容"):
                        extracted_text = gr.Textbox(
                            label="",
                            lines=20,
                            interactive=True,
                            elem_classes="fixed-height"
                        )
                    
                    with gr.TabItem("批改结果"):
                        rating_result = gr.Markdown(
                            "## 批改结果\n_等待批改中..._",
                            elem_classes="fixed-height"  # 应用 fixed-height 类
                        )

                with gr.Row():
                    download_text = gr.File(label="下载文本", visible=False)
                    download_rate = gr.File(label="下载批改", visible=False)



        # 历史记录面板
        with gr.Accordion("批改历史", open=False):
            history_table = gr.Dataframe(
                headers=["题目", "时间", "文本", "批改"],
                datatype=["str", "str", "file", "file"],
                interactive=False
            )

        # 事件处理
        def update_gallery(files):
            return files, files  # 返回更新后的Gallery和State

        def full_process(files, history):
            try:
                validate_image_files(files)
                
                # 实时显示处理进度
                yield {
                    process_status: "**当前状态**: 正在处理图片...",
                    image_gallery: files  # 确保在outputs中包含image_gallery
                }

                # 流式提取文本
                text_gen = stream_extract_text(files)
                full_text = ""
                for partial_text in text_gen:
                    full_text = partial_text
                    yield {
                        process_status: "**当前状态**: 正在提取文本...",
                        extracted_text: full_text
                    }

                # 分割标题和内容
                lines = full_text.split("\n", 1)
                title = lines[0].strip() or "未命名作文"
                content = lines[1].strip() if len(lines) > 1 else ""

                # 流式生成批改
                rate_gen = stream_rate_text(content)
                full_rate = ""
                for partial_rate in rate_gen:
                    full_rate = partial_rate
                    yield {
                        process_status: "**当前状态**: 正在生成批改...",
                        rating_result: f"## 批改结果\n{full_rate}"
                    }

                # 保存结果
                text_path = safe_save(content, TEXTS_DIR, title)
                rate_path = safe_save(full_rate, RATES_DIR, f"{title}_批改")

                # 更新历史记录
                new_entry = {
                    "title": title,
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "text_path": text_path,
                    "rate_path": rate_path
                }
                updated_history = history + [new_entry]
                save_history(updated_history)

                yield {
                    process_status: "**当前状态**: 批改完成！",
                    download_text: text_path,
                    download_rate: rate_path,
                    history_table: pd.DataFrame(updated_history),
                    history_state: updated_history
                }

            except Exception as e:
                yield {process_status: f"**错误**: {str(e)}"}

        def reset_ui():
            return [
                None,  # image_gallery
                "",    # extracted_text
                "## 批改结果\n_等待批改中..._",  # rating_result
                None,  # download_text
                None,  # download_rate
                "**当前状态**: 等待上传图片"  # process_status
            ]

        # 组件绑定（关键修复部分）
        upload_btn.upload(
            fn=update_gallery,
            inputs=upload_btn,
            outputs=[image_gallery, uploaded_files],  # 明确指定两个输出
            queue=False
        )

        start_btn.click(
            fn=full_process,
            inputs=[uploaded_files, history_state],
            outputs=[
                process_status,    # 输出1
                image_gallery,     # 输出2（新增）
                extracted_text,    # 输出3
                rating_result,     # 输出4
                download_text,     # 输出5
                download_rate,     # 输出6
                history_table,     # 输出7
                history_state      # 输出8
            ]
        )

        next_btn.click(
            fn=reset_ui,
            outputs=[
                image_gallery,     # 输出1
                extracted_text,    # 输出2
                rating_result,     # 输出3
                download_text,     # 输出4
                download_rate,     # 输出5
                process_status     # 输出6
            ],
            queue=False
        )

    return demo

# --- 启动应用 ---
if __name__ == "__main__":
    app = create_interface()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False
    )

