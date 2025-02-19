

```markdown
# 作文智能批改助手使用指南

![Gradio界面预览](https://via.placeholder.com/800x400.png?text=Gradio+UI+Preview)

## 📋 项目概述
基于Gradio和ModelScope API开发的AI作文批改系统，提供以下功能：
- **图片上传**：支持多张作文照片上传
- **智能识别**：自动提取图片中的作文文本
- **AI批改**：生成包含评分和修改建议的批改报告
- **历史管理**：自动保存每次批改记录
- **文件导出**：支持文本和批改结果下载

## 🛠️ 环境准备

### 最低要求
- Python 3.10+
- 磁盘空间：至少500MB可用空间
- 内存：4GB以上

### 推荐配置
- CPU：4核以上
- 内存：8GB+
- 网络：10Mbps+互联网连接

## ⚙️ 安装部署

1. 克隆仓库
```bash
git clone https://github.com/LandyLee-gdut/essay_grader.git
cd essay-grader
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置文件
```bash
# 创建.env文件
echo "MODELSCOPE_API_ENDPOINT=https://api-inference.modelscope.cn/v1/" > .env
echo "MODELSCOPE_API_KEY=your_api_key_here" >> .env

# 创建提示模板
mkdir -p code
echo "请根据以下标准批改作文：[你的评分标准]" > code/prompt.txt
```

## 🚀 快速启动
```bash
python gradio_ui.py
```
启动后访问 [http://localhost:7860](http://localhost:7860)

## 🖥️ 界面导览
![界面分区说明](https://via.placeholder.com/800x400.png?text=UI+Layout+Explanation)
1. **控制区**（左侧）
   - 图片上传按钮
   - 历史批改列表
2. **工作区**（右侧）
   - 实时处理状态
   - 文本提取显示
   - AI批改结果

## 🧑💻 使用教程

### 1. 上传作文图片
1. 点击`上传作文图片`按钮
2. 选择1-5张清晰的照片（支持JPG/PNG格式）
3. 确认图片在左侧预览区正常显示

### 2. 开始批改
点击`开始批改`按钮后，系统将：
1. 自动识别图片中的作文内容（约1-2秒/页）
2. 实时显示识别进度
3. 生成AI批改报告（约3-5秒）

### 3. 查看结果
- **提取文本**：右侧文本区查看识别结果
- **批改报告**：包含：
  ```markdown
  ## 综合评分：85/100
  ### 优点
  - 主题明确，结构清晰
  - 修辞手法运用得当
  
  ### 改进建议
  - 加强段落过渡衔接
  - 注意标点符号使用
  ```

### 4. 文件管理
- **下载结果**：
  - 点击`下载文本`保存原始作文
  - 点击`下载批改`保存批改报告
- **历史记录**：
  - 展开底部`批改历史`面板
  - 支持按时间排序和文件检索

### 5. 开始新批改
点击`批改下一篇`按钮清空当前内容

## 🔧 高级配置

### 修改模型设置
编辑`.env`文件：
```ini
# 更换为其他支持的模型
EXTRACTION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
RATING_MODEL=deepseek-ai/DeepSeek-R1
```

### 自定义评分标准
修改`code/prompt.txt`：
```text
请根据以下维度批改：
1. 主题明确（30%）
2. 结构合理（20%）
3. 语言表达（30%）
4. 创意亮点（20%）
附加要求：
- 指出至少2个优点
- 提出3条改进建议
```

## 🚨 常见问题

### 图片上传失败
- 确保图片小于5MB
- 检查文件格式是否为JPG/PNG
- 尝试重新拍摄清晰的照片

### 批改结果不理想
- 调整拍摄角度，保证文字清晰
- 分页拍摄多张局部特写
- 检查prompt.txt中的评分标准

### API连接问题
```bash
# 测试API连通性
curl -X POST ${MODELSCOPE_API_ENDPOINT} \
  -H "Authorization: Bearer ${MODELSCOPE_API_KEY}" \
  -d '{"model":"Qwen/Qwen2.5-VL-7B-Instruct"}'
```

## 📜 许可协议
本项目采用 [MIT License](LICENSE)，欢迎二次开发，但需保留原始署名。

```

> 提示：本指南需配合实际截图完善，建议：
> 1. 添加界面各区域的标注说明图
> 2. 补充典型批改结果示例
> 3. 增加操作流程图解
> 4. 提供API申请指导链接