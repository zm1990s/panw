---
name: "translate-pptx"
description: "将 PPT（.pptx）翻译成简体中文，遵循\"信雅达\"原则，保留 Agent、LLM 等专业术语不译。当用户说\"翻译这个 PPT\"、\"把 PPT 翻译成中文\"或类似需求时使用。"
---

# PPT 简体中文翻译 Skill

## 角色定位
你是一位专业的科技内容翻译顾问，擅长将演示文稿翻译成准确、流畅、优雅的简体中文，遵循严复提出的**信雅达**三原则：
- **信（Faithful）**：忠实原意，不增删、不歪曲
- **雅（Elegant）**：语言得体，符合中文演示文稿的表达习惯
- **达（Expressive）**：通顺流畅，读来自然，避免翻译腔

---

## 触发条件
用户上传了一个 `.pptx` 文件，或提供了文件路径，要求将其中的内容翻译成简体中文。

---

## ⚠️ 格式保护铁律（最高优先级）

**翻译过程中绝对不能改变的内容：**

| 属性 | 说明 |
|------|------|
| 字体名称 | 不得替换字体 |
| 字号（font size） | 每个 run 的字号必须与原文完全一致 |
| 字体颜色（RGB） | 保持原 RGB 值，不得修改 |
| 加粗 / 斜体 / 下划线 | 保持每个 run 的原始状态 |
| 文本框位置与尺寸 | 不得移动、缩放任何形状 |
| 段落对齐方式 | left / center / right / justify 保持不变 |
| 段落间距 / 行距 | space_before / space_after / line_spacing 保持不变 |
| 项目符号与缩进 | 列表层级、bullet 样式、indent 不变 |
| 图片 / 图标 / 形状 | 完全不动，只修改文字 run 的 text 属性 |
| 幻灯片背景 | 不触碰 |
| 动画 / 切换效果 | 不触碰 |
| 备注（Notes） | 如备注含需翻译文本则同样翻译，格式不变 |

**唯一允许修改的属性是 `run.text` 的文字内容本身。**

---

## 执行步骤

### Step 1 — 确认输入文件
- 在 uploads 目录中定位 `.pptx` 文件（bash 路径：`/sessions/*/mnt/uploads/`）
- 如果用户未明确指定文件，列出可用文件并询问

### Step 2 — 安装依赖
```bash
pip install python-pptx --break-system-packages -q
```

### Step 3 — 安全提取文本（只读 text，不碰格式）

> ⚠️ **必须使用递归方式处理分组形状（Group shapes，shape_type == 6）**，否则嵌套在组内的文本（如图表标签、流程图节点、网络拓扑图中的标注）将被漏译。ID 使用路径编码：组内子元素用 `_g{child_idx}` 追加，可无限递归嵌套。

```python
from pptx import Presentation
import json, re

def needs_translation(text: str) -> bool:
    """判断文本是否含有需要翻译的外文字符（非中文、非数字、非符号）"""
    if not text or not text.strip():
        return False
    # 跳过纯数字、百分比、URL、代码
    if re.match(r'^[\d\s%$€¥.,/:@#()\-_+=\[\]{}|\\<>""\'\'•·–—…™®©]+$', text):
        return False
    if text.startswith(('http', 'www', '//', '#!')):
        return False
    # 含有英文字母则需翻译
    return bool(re.search(r'[A-Za-z]', text))

def extract_from_text_frame(tf, path_prefix, items):
    """从 text_frame 提取文本，path_prefix 已含 slide_idx 和 shape 路径"""
    for para_idx, para in enumerate(tf.paragraphs):
        for run_idx, run in enumerate(para.runs):
            if needs_translation(run.text):
                items.append({
                    "id": f"{path_prefix}_{para_idx}_{run_idx}",
                    "original": run.text
                })

def extract_from_shape(shape, slide_idx, shape_path, items):
    """递归提取形状（含 Group shapes）内的所有文本"""
    # 普通文本框
    if shape.has_text_frame:
        extract_from_text_frame(shape.text_frame, f"{slide_idx}_{shape_path}", items)
    # 表格
    if hasattr(shape, 'has_table') and shape.has_table:
        for row_idx, row in enumerate(shape.table.rows):
            for col_idx, cell in enumerate(row.cells):
                path = f"tbl_{slide_idx}_{shape_path}_{row_idx}_{col_idx}"
                extract_from_text_frame(cell.text_frame, path, items)
    # ✅ 分组形状（Group shapes）— 递归处理所有子元素
    if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP = 6
        for child_idx, child in enumerate(shape.shapes):
            extract_from_shape(child, slide_idx, f"{shape_path}_g{child_idx}", items)

def extract_texts(pptx_path: str) -> list:
    """提取所有含外文的文本，返回带路径 ID 的列表"""
    prs = Presentation(pptx_path)
    items = []
    for slide_idx, slide in enumerate(prs.slides):
        for shape_idx, shape in enumerate(slide.shapes):
            extract_from_shape(shape, slide_idx, str(shape_idx), items)
    return items

items = extract_texts(INPUT_PATH)
print(f"Total items to translate: {len(items)}")
with open('/tmp/texts_to_translate.json', 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
print(json.dumps(items, ensure_ascii=False, indent=2))
```

### Step 4 — 批量翻译成简体中文

将提取的文本按每批 15 条分组，以 JSON 数组格式翻译，确保一一对应：

**翻译输入格式：**
```json
["Key Findings", "Boost R&D Efficiency", "Summary & Outlook"]
```

**翻译输出格式（严格对应）：**
```json
["核心发现", "提升研发效率", "总结与展望"]
```

**翻译规则：**

1. **保留不译的术语**（原词不变，大小写保持）：
   - AI 技术类：`Agent`、`Multi-Agent`、`LLM`、`GPT`、`RAG`、`Prompt`、`Fine-tuning`、`Token`、`Embedding`、`MCP`、`AI`、`AGI`
   - 产品品牌：`Claude`、`ChatGPT`、`OpenAI`、`Anthropic`、`GitHub`、`Google`、`Microsoft`
   - 通用缩写：`API`、`SDK`、`SaaS`、`PaaS`、`DevOps`、`CI/CD`、`CEO`、`CTO`、`KPI`、`OKR`、`ROI`
   - 编程语言：`Python`、`JavaScript`、`TypeScript`、`Go`、`Rust`

2. **不翻译的内容**（原样保留）：
   - 纯数字、百分比、日期
   - URL、邮箱地址
   - 代码片段

3. **混合文本处理**：
   - 英文句子中夹有保留术语时，翻译其余部分，术语原样保留
   - 例："Build an Agent pipeline" → "构建 Agent 流水线"

4. **信雅达具体操作：**
   - 标题：简洁有力，4–10 字为佳，避免机械直译
   - 正文：符合中文演示文稿习惯，动宾结构优先
   - 避免翻译腔：如 "Enhance the efficiency of the team" → "提升团队效率"（不是"增强团队的效率"）
   - 专业术语用业界通行译法：如 "Workflow" → "工作流"，"Embedding" 保留不译

### Step 5 — 格式安全写回

**核心原则：只修改 `run.text`，其余属性一律不碰。写回同样需要递归处理 Group shapes，与提取时使用完全相同的路径编码逻辑。**

```python
from pptx import Presentation
from lxml import etree

def safe_set_text(run, new_text: str):
    """
    安全地只替换文字内容，严格保留所有格式属性。
    通过底层 XML 操作 <a:t> 节点，避免高层 API 意外清除格式。
    """
    nsmap = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    t_elem = run._r.find('.//a:t', nsmap)
    if t_elem is not None:
        t_elem.text = new_text
    else:
        run.text = new_text  # fallback

def apply_to_text_frame(tf, path_prefix, translations, applied):
    for para_idx, para in enumerate(tf.paragraphs):
        for run_idx, run in enumerate(para.runs):
            key = f"{path_prefix}_{para_idx}_{run_idx}"
            if key in translations:
                safe_set_text(run, translations[key])
                applied.add(key)

def apply_to_shape(shape, slide_idx, shape_path, translations, applied):
    """递归写回翻译（含 Group shapes），路径编码与提取时完全一致"""
    if shape.has_text_frame:
        apply_to_text_frame(shape.text_frame, f"{slide_idx}_{shape_path}", translations, applied)
    if hasattr(shape, 'has_table') and shape.has_table:
        for row_idx, row in enumerate(shape.table.rows):
            for col_idx, cell in enumerate(row.cells):
                path = f"tbl_{slide_idx}_{shape_path}_{row_idx}_{col_idx}"
                apply_to_text_frame(cell.text_frame, path, translations, applied)
    # ✅ 分组形状（Group shapes）— 递归写回
    if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP = 6
        for child_idx, child in enumerate(shape.shapes):
            apply_to_shape(child, slide_idx, f"{shape_path}_g{child_idx}", translations, applied)

def write_translations(pptx_path: str, output_path: str, translations: dict):
    """
    translations: {id: translated_text} 的字典
    只修改 text，格式零变化，完整覆盖 Group shapes 内嵌文本
    """
    prs = Presentation(pptx_path)
    applied = set()

    for slide_idx, slide in enumerate(prs.slides):
        for shape_idx, shape in enumerate(slide.shapes):
            apply_to_shape(shape, slide_idx, str(shape_idx), translations, applied)

    # 处理备注页
    for slide_idx, slide in enumerate(prs.slides):
        if slide.has_notes_slide:
            notes_tf = slide.notes_slide.notes_text_frame
            for para_idx, para in enumerate(notes_tf.paragraphs):
                for run_idx, run in enumerate(para.runs):
                    key = f"notes_{slide_idx}_{para_idx}_{run_idx}"
                    if key in translations:
                        safe_set_text(run, translations[key])
                        applied.add(key)

    prs.save(output_path)
    not_applied = set(translations.keys()) - applied
    print(f"✅ Translation complete: {output_path}")
    print(f"   Applied: {len(applied)}, Not matched: {len(not_applied)}")
    if not_applied:
        print(f"   Unmatched keys: {not_applied}")

write_translations(INPUT_PATH, OUTPUT_PATH, translation_dict)
```

### Step 6 — 格式验证

```python
from pptx import Presentation

def verify_format_integrity(original_path: str, translated_path: str):
    """对比原文件和译文文件的格式属性，确认零变化"""
    orig = Presentation(original_path)
    tran = Presentation(translated_path)

    issues = []
    for s_idx, (s_orig, s_tran) in enumerate(zip(orig.slides, tran.slides)):
        for sh_idx, (sh_orig, sh_tran) in enumerate(zip(s_orig.shapes, s_tran.shapes)):
            if (sh_orig.left, sh_orig.top, sh_orig.width, sh_orig.height) != \
               (sh_tran.left, sh_tran.top, sh_tran.width, sh_tran.height):
                issues.append(f"第 {s_idx+1} 页 形状 {sh_idx+1}：位置或尺寸发生变化！")

            if sh_orig.has_text_frame and sh_tran.has_text_frame:
                for p_idx, (p_orig, p_tran) in enumerate(
                    zip(sh_orig.text_frame.paragraphs, sh_tran.text_frame.paragraphs)
                ):
                    for r_idx, (r_orig, r_tran) in enumerate(zip(p_orig.runs, p_tran.runs)):
                        if r_orig.font.size != r_tran.font.size:
                            issues.append(f"第 {s_idx+1} 页 形状 {sh_idx+1} 段落 {p_idx} Run {r_idx}：字号变化！")
                        if r_orig.font.bold != r_tran.font.bold:
                            issues.append(f"第 {s_idx+1} 页 形状 {sh_idx+1} 段落 {p_idx} Run {r_idx}：加粗状态变化！")
                        if r_orig.font.color.type != r_tran.font.color.type:
                            issues.append(f"第 {s_idx+1} 页 形状 {sh_idx+1} 段落 {p_idx} Run {r_idx}：字色类型变化！")

    if issues:
        print("⚠️ 发现格式问题：")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ 格式完整性验证通过，零格式变化。")
    return issues

verify_format_integrity(INPUT_PATH, OUTPUT_PATH)
```

如验证发现问题，立即排查并修复，重新生成文件。

### Step 7 — 呈现结果

使用 `mcp__cowork__present_files` 工具将输出文件呈现给用户，并简短说明：
- 翻译了多少张幻灯片
- 发现并处理了哪些 Group shapes（含嵌套层数）
- 保留了哪些术语原词
- 格式验证结果

---

## 常见术语翻译参考

| 原文 | 简体中文译文 | 备注 |
|------|-------------|------|
| Workflow | 工作流 | |
| Use Cases | 落地场景 / 应用场景 | 根据语境选择 |
| Foundation Model | 基础模型 | |
| Inference | 推理 | |
| Deployment | 部署 | |
| Benchmark | 基准测试 | |
| Hallucination | 幻觉 | |
| Context Window | 上下文窗口 | |
| Pipeline | 流水线 / Pipeline | 技术场景保留原词 |
| Orchestration | 编排 | |
| Retrieval | 检索 | |
| Evaluation | 评估 | |
| Scalability | 可扩展性 | |
| Latency | 延迟 | |
| Throughput | 吞吐量 | |

---

## 错误处理

- 文件损坏无法读取 → 告知用户并建议重新上传
- 混合语言文本 → 只翻译非中文部分，保留术语原词
- 格式验证不通过 → 定位问题 run，使用 `safe_set_text` 重写，直到验证通过
- 译文过长导致视觉溢出 → 适当精简译文但保持原意，**绝不**缩小字号或调整文本框
- Group shapes 漏译 → 检查 `shape.shape_type == 6` 的递归逻辑，确认路径编码与提取时一致

