"""Generate README architecture diagrams directly as PNG files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)

FONT_PATHS = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FONT = {
    "title": load_font(44),
    "subtitle": load_font(22),
    "h1": load_font(28),
    "h2": load_font(21),
    "body": load_font(17),
    "small": load_font(14),
    "tiny": load_font(12),
}

COLOR = {
    "text": "#10204a",
    "muted": "#53627a",
    "blue": "#2563eb",
    "blue2": "#eff6ff",
    "green": "#16a34a",
    "green2": "#f0fdf4",
    "orange": "#f97316",
    "orange2": "#fff7ed",
    "purple": "#8b5cf6",
    "purple2": "#faf5ff",
    "gray": "#64748b",
    "gray2": "#f8fafc",
    "red": "#ef4444",
    "red2": "#fff1f2",
}


def new_canvas(width: int, height: int, title: str, subtitle: str | None = None):
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((width / 2, 30), title, font=FONT["title"], fill=COLOR["text"], anchor="ma")
    if subtitle:
        draw.text((width / 2, 82), subtitle, font=FONT["subtitle"], fill=COLOR["muted"], anchor="ma")
    return image, draw


def centered_text(draw: ImageDraw.ImageDraw, xy, text: str, font, fill=COLOR["text"]):
    x1, y1, x2, y2 = xy
    lines = str(text).split("\n")
    heights = []
    widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    total_height = sum(heights) + 6 * (len(lines) - 1)
    y = y1 + (y2 - y1 - total_height) / 2
    for line, width, height in zip(lines, widths, heights):
        draw.text((x1 + (x2 - x1 - width) / 2, y), line, font=font, fill=fill)
        y += height + 6


def box(draw, xy, text="", fill="blue2", outline="blue", font_name="body", radius=14, width=2):
    draw.rounded_rectangle(
        xy,
        radius=radius,
        fill=COLOR.get(fill, fill),
        outline=COLOR.get(outline, outline),
        width=width,
    )
    if text:
        centered_text(draw, xy, text, FONT[font_name])


def arrow(draw, start, end, color="blue", width=3):
    draw.line([start, end], fill=COLOR[color], width=width)
    x1, y1 = start
    x2, y2 = end
    import math

    angle = math.atan2(y2 - y1, x2 - x1)
    size = 12
    points = []
    for delta in (2.55, -2.55):
        points.append((x2 + size * math.cos(angle + delta), y2 + size * math.sin(angle + delta)))
    draw.polygon([(x2, y2), points[0], points[1]], fill=COLOR[color])


def save(image: Image.Image, name: str):
    image.save(OUT / name, "PNG")


def draw_architecture():
    image, draw = new_canvas(
        1800,
        1120,
        "Superset Agent Service 架构图",
        "MCP-enabled Agent Sidecar Architecture · Agent + RAG · Plan + ReAct + Reflection Hybrid Workflow",
    )
    box(draw, (220, 120, 1580, 205), "", "blue2", "blue", "h2")
    draw.text((250, 150), "接入层 (Clients)", font=FONT["h2"], fill=COLOR["text"])
    for x, text in [(430, "Superset UI"), (640, "Legacy System UI"), (850, "API / SDK"), (1060, "Chat Platform")]:
        box(draw, (x, 145, x + 170, 185), text, "gray2", "blue", "body")

    box(draw, (40, 300, 250, 860), "", "green2", "green", "h2")
    draw.text((78, 326), "输入层 (Input)", font=FONT["h2"], fill=COLOR["text"])
    for y, text in [
        (390, "用户问题"),
        (485, "Dashboard / Chart\n上下文"),
        (590, "Filters / Time Range"),
        (690, "登录身份 / 权限"),
    ]:
        box(draw, (70, y, 220, y + 62), text, "green2", "green", "body")

    box(draw, (300, 245, 1450, 900), "", "gray2", "blue", width=2)
    draw.text((725, 272), "Agent 服务核心层 (Core)", font=FONT["h1"], fill=COLOR["text"])

    box(draw, (345, 315, 1405, 420), "", "blue2", "blue", "h2")
    draw.text((650, 332), "1. LangGraph 编排器 (Orchestrator)", font=FONT["h2"], fill=COLOR["text"])
    steps = ["Context Intake", "Skill Routing", "Plan", "ReAct Tool Loop", "Reflection", "Final Answer", "Progress Control"]
    x = 370
    for step in steps:
        box(draw, (x, 360, x + 135, 400), step, "gray2", "blue", "tiny")
        x += 145

    box(draw, (345, 450, 1405, 560), "", "purple2", "purple", "h2")
    draw.text((705, 467), "2. Skills 层 (Business Skills)", font=FONT["h2"], fill=COLOR["text"])
    for x, text in [
        (375, "dashboard_explainer"),
        (585, "metric_investigator"),
        (795, "text_to_sql"),
        (965, "cost_monitor"),
        (1145, "error_investigator"),
    ]:
        box(draw, (x, 500, x + 180, 535), text, "purple2", "purple", "tiny")

    box(draw, (345, 590, 1405, 690), "", "orange2", "orange", "h2")
    draw.text((650, 607), "3. Agent + RAG 能力层 (Capabilities)", font=FONT["h2"], fill=COLOR["text"])
    for x, text in [(390, "对话管理"), (540, "工具调用"), (690, "RAG 检索"), (840, "SQL 生成"), (990, "Reflection 自检"), (1190, "Trace 记录")]:
        box(draw, (x, 640, x + 120, 675), text, "orange2", "orange", "small")

    box(draw, (345, 725, 735, 845), "", "green2", "green", "h2")
    draw.text((485, 742), "4. 工具层 (Tools)", font=FONT["h2"], fill=COLOR["text"])
    for x, text in [(375, "Superset MCP"), (520, "SQL Guard"), (645, "Policy Guard")]:
        box(draw, (x, 780, x + 115, 820), text, "green2", "green", "tiny")

    box(draw, (775, 725, 1405, 845), "", "purple2", "purple", "h2")
    draw.text((1010, 742), "5. RAG 知识层 (Knowledge)", font=FONT["h2"], fill=COLOR["text"])
    for x, text in [(815, "指标口径"), (955, "业务术语"), (1095, "Dashboard 文档"), (1260, "向量索引")]:
        box(draw, (x, 780, x + 125, 820), text, "purple2", "purple", "small")

    box(draw, (345, 870, 1405, 895), "6. 模型层：LLM Gateway · OpenAI · Qwen · DeepSeek · Claude", "blue2", "blue", "body")

    box(draw, (1500, 300, 1750, 860), "", "green2", "green", "h2")
    draw.text((1540, 326), "外部服务层", font=FONT["h2"], fill=COLOR["text"])
    draw.text((1540, 352), "(External Services)", font=FONT["body"], fill=COLOR["muted"])
    for y, text in [
        (385, "Superset MCP Server"),
        (470, "Superset API / Metadata"),
        (555, "业务数据库"),
        (640, "Vector DB"),
        (725, "LLM Provider"),
        (810, "Legacy API"),
    ]:
        box(draw, (1530, y, 1720, y + 50), text, "green2", "green", "tiny")

    box(draw, (220, 960, 1580, 1055), "", "gray2", "gray", "h2")
    draw.text((710, 978), "基础设施层 (Platform & Governance)", font=FONT["h2"], fill=COLOR["text"])
    for x, text in [
        (270, "Auth / RBAC"),
        (440, "Admin Config"),
        (620, "Audit Logger"),
        (800, "Metrics Collector"),
        (1010, "Run / Trace Store"),
        (1230, "Alerts"),
        (1390, "Superset Usage Dashboard"),
    ]:
        box(draw, (x, 1005, x + 145, 1045), text, "gray2", "blue", "tiny")

    arrow(draw, (250, 580), (300, 580), "green")
    arrow(draw, (1450, 580), (1500, 580), "orange")
    arrow(draw, (900, 900), (900, 960), "gray")
    save(image, "architecture-agent-rag.png")


def simple_flow(name: str, title: str, subtitle: str, boxes: Iterable[tuple[str, str, str]]):
    image, draw = new_canvas(1400, 760, title, subtitle)
    x = 90
    y = 250
    previous = None
    for heading, body, color in boxes:
        box(draw, (x, y, x + 230, y + 145), f"{heading}\n\n{body}", f"{color}2" if color != "blue" else "blue2", color, "body")
        if previous:
            arrow(draw, previous, (x, y + 72), "blue")
        previous = (x + 230, y + 72)
        x += 310
    save(image, name)


def draw_workflow():
    simple_flow(
        "workflow.png",
        "执行流程图",
        "一次用户提问从 UI 到 Agent、RAG、MCP、Reflection、Trace 的链路",
        [
            ("Context Intake", "question\ncontext\nidentity", "orange"),
            ("Skill + Plan", "选择 Skill\n规划步骤", "purple"),
            ("ReAct Loop", "MCP\nRAG\nSQL Guard", "green"),
            ("Reflection", "检查证据\n风险\n成本", "orange"),
        ],
    )


def draw_skills():
    image, draw = new_canvas(1300, 720, "Skills 业务能力图", "Skill 负责业务目标，Tool 负责具体动作")
    box(draw, (80, 150, 250, 215), "User Question", "blue2", "blue", "body")
    box(draw, (360, 150, 540, 215), "Skill Router", "purple2", "purple", "body")
    arrow(draw, (250, 183), (360, 183), "blue")
    skills = [
        ("dashboard_explainer", 650, 95),
        ("metric_investigator", 650, 175),
        ("text_to_sql", 650, 255),
        ("cost_monitor", 650, 335),
        ("error_investigator", 650, 415),
    ]
    for skill, x, y in skills:
        box(draw, (x, y, x + 230, y + 52), skill, "purple2", "purple", "small")
        arrow(draw, (540, 183), (x, y + 26), "blue")
    box(draw, (970, 175, 1210, 430), "Tool Registry\n\nSuperset MCP\nSQL Guard\nRAG Retriever\nCustom Tools\nPolicy Guard", "green2", "green", "body")
    for _, x, y in skills[:4]:
        arrow(draw, (x + 230, y + 26), (970, 265), "green")
    box(draw, (250, 570, 1050, 635), "Skill = 业务能力流程；Tool = 具体动作。Skill 组合多个 Tool，并进入 Trace / Metrics / Audit。", "orange2", "orange", "body")
    save(image, "skills.png")


def draw_modules():
    image, draw = new_canvas(1300, 760, "模块依赖图", "FastAPI 包内模块边界")
    levels = [
        [(600, "main.py")],
        [(600, "api/router.py")],
        [(150, "auth"), (330, "agents"), (510, "skills"), (690, "tools"), (870, "runs"), (1050, "admin")],
        [(250, "rag"), (450, "guards"), (650, "metrics"), (850, "audit")],
        [(500, "db"), (720, "config")],
    ]
    ys = [120, 230, 360, 500, 630]
    coords = {}
    for level, y in zip(levels, ys):
        for x, text in level:
            box(draw, (x - 75, y, x + 75, y + 50), text, "blue2", "blue", "body")
            coords[text] = (x, y + 25)
    for src, dst in [
        ("main.py", "api/router.py"),
        ("api/router.py", "auth"),
        ("api/router.py", "agents"),
        ("api/router.py", "runs"),
        ("api/router.py", "admin"),
        ("agents", "skills"),
        ("agents", "tools"),
        ("agents", "rag"),
        ("agents", "guards"),
        ("agents", "metrics"),
        ("agents", "audit"),
        ("runs", "db"),
        ("admin", "config"),
        ("db", "config"),
    ]:
        arrow(draw, coords[src], coords[dst], "gray")
    save(image, "modules.png")


def draw_data_model():
    image, draw = new_canvas(1400, 850, "数据模型规划图", "Agent Runs、Events、Model Calls、Tool Calls、Audit、Usage 的关系")
    items = [
        ("users", "id\nemail\ntenant_id\nrole", 80, 120, "green"),
        ("agents", "id\nname\ndefault_model\nreflection_policy", 360, 120, "purple"),
        ("agent_runs", "id\nuser_id / agent_id\nstatus\ntotal_tokens\ntotal_cost_usd", 710, 100, "blue"),
        ("agent_run_events", "run_id\nevent_type\npayload_json", 80, 390, "blue"),
        ("agent_model_calls", "provider / model\ntokens\ncost_usd", 350, 390, "orange"),
        ("agent_tool_calls", "tool_name\ninput_json\noutput_json", 620, 390, "green"),
        ("reflection_events", "finding\ndecision\nconfidence", 890, 390, "purple"),
        ("agent_audit_logs", "user_id\naction\nmetadata_json", 250, 650, "green"),
        ("agent_usage_daily", "day\nuser_id\nmodel\ncost", 700, 650, "orange"),
    ]
    coords = {}
    for name, fields, x, y, color in items:
        box(draw, (x, y, x + 220, y + 145), f"{name}\n{fields}", f"{color}2" if color != "blue" else "blue2", color, "small")
        coords[name] = (x + 110, y + 72)
    for dst in ["agent_run_events", "agent_model_calls", "agent_tool_calls", "reflection_events"]:
        arrow(draw, coords["agent_runs"], coords[dst], "gray")
    for dst in ["agent_runs", "agent_audit_logs", "agent_usage_daily"]:
        arrow(draw, coords["users"], coords[dst], "gray")
    arrow(draw, coords["agents"], coords["agent_runs"], "gray")
    save(image, "data-model.png")


def draw_deployment():
    image, draw = new_canvas(1400, 760, "部署集成图", "Superset、Agent Service、MCP、数据服务和 LLM 的部署关系")
    box(draw, (70, 140, 300, 570), "Client Layer\n\nSuperset UI\nLegacy System UI\nChat Platform", "blue2", "blue", "body")
    box(draw, (430, 120, 720, 590), "Agent Service Runtime\n\nFastAPI Agent Service\nLangGraph Workflow\nSkills + Tool Registry\nGuards + Trace + Metrics", "purple2", "purple", "body")
    box(draw, (850, 120, 1080, 590), "Superset Runtime\n\nSuperset MCP Server\nSuperset API\nSuperset Metadata DB", "green2", "green", "body")
    box(draw, (1170, 120, 1350, 590), "Data / AI\n\nBusiness DB\nVector DB\nUsage DB\nLLM Provider", "orange2", "orange", "body")
    arrow(draw, (300, 330), (430, 330), "blue")
    arrow(draw, (720, 250), (850, 250), "green")
    arrow(draw, (1080, 250), (1170, 230), "green")
    arrow(draw, (720, 420), (1170, 430), "orange")
    save(image, "deployment.png")


def draw_governance():
    simple_flow(
        "governance.png",
        "权限治理图",
        "身份、角色、工具权限和 SQL 安全检查链路",
        [
            ("Request", "用户请求", "blue"),
            ("Auth", "解析身份\n租户\n角色", "green"),
            ("Policy Guard", "Skill / Tool\n权限检查", "orange"),
            ("SQL Guard", "只读查询\n敏感字段\n限制行数", "orange"),
        ],
    )


def draw_observability():
    image, draw = new_canvas(1350, 760, "可观测性链路图", "Run Trace、Metrics、Audit 到 Superset Usage Dashboard")
    box(draw, (70, 140, 240, 205), "Agent Run", "purple2", "purple", "body")
    events = [("Run Events", 370, 90), ("Model Calls", 370, 170), ("Tool Calls", 370, 250), ("Reflection Events", 370, 330), ("Audit Logs", 370, 410)]
    for text, x, y in events:
        box(draw, (x, y, x + 180, y + 54), text, "blue2", "blue", "body")
        arrow(draw, (240, 172), (x, y + 27), "blue")
    box(draw, (680, 240, 850, 330), "Usage DB\ntrace / metrics / audit", "green2", "green", "body")
    for _, x, y in events:
        arrow(draw, (x + 180, y + 27), (680, 285), "gray")
    for text, x, y in [("Run Trace Page", 1010, 150), ("Superset Usage Dashboard", 1010, 260), ("Alerts", 1010, 370)]:
        box(draw, (x, y, x + 230, y + 58), text, "orange2", "orange", "body")
        arrow(draw, (850, 285), (x, y + 29), "orange")
    box(draw, (250, 590, 1100, 650), "回答：为什么慢 · 为什么贵 · 为什么失败 · 哪个用户最多 · 哪个模型成本最高", "purple2", "purple", "body")
    save(image, "observability.png")


def draw_roadmap():
    simple_flow(
        "roadmap.png",
        "演进路线图",
        "先跑通链路，再做观测；先管住权限，再增强智能",
        [
            ("阶段 1: MVP", "Superset MCP\nBasic LangGraph\nRun Trace", "blue"),
            ("阶段 2: 可观测性", "Usage DB\nToken / Cost\nDashboard", "green"),
            ("阶段 3: 安全治理", "SSO / JWT\nRBAC / Tenant\nSQL AST Guard", "orange"),
            ("阶段 4: 智能能力", "RAG\nReflection\nEvaluation", "purple"),
        ],
    )


def icon(draw, kind: str, x: int, y: int, color: str):
    """Draw a small line icon in the diagram's simple enterprise style."""
    c = COLOR[color]
    if kind == "user":
        draw.ellipse((x + 9, y, x + 27, y + 18), outline=c, width=3)
        draw.arc((x, y + 18, x + 36, y + 48), 200, -20, fill=c, width=3)
    elif kind == "chat":
        draw.rounded_rectangle((x, y + 5, x + 38, y + 30), radius=6, outline=c, width=3)
        draw.line((x + 12, y + 30, x + 6, y + 42), fill=c, width=3)
        for i in range(3):
            draw.ellipse((x + 9 + i * 10, y + 16, x + 13 + i * 10, y + 20), fill=c)
    elif kind == "api":
        draw.rectangle((x + 4, y + 8, x + 36, y + 36), outline=c, width=3)
        draw.line((x + 12, y + 18, x + 4, y + 24), fill=c, width=3)
        draw.line((x + 12, y + 30, x + 4, y + 24), fill=c, width=3)
        draw.line((x + 28, y + 18, x + 36, y + 24), fill=c, width=3)
        draw.line((x + 28, y + 30, x + 36, y + 24), fill=c, width=3)
    elif kind == "webhook":
        draw.ellipse((x + 4, y + 5, x + 18, y + 19), outline=c, width=3)
        draw.ellipse((x + 22, y + 5, x + 36, y + 19), outline=c, width=3)
        draw.ellipse((x + 13, y + 28, x + 27, y + 42), outline=c, width=3)
        draw.line((x + 16, y + 17, x + 18, y + 30), fill=c, width=3)
        draw.line((x + 27, y + 17, x + 24, y + 30), fill=c, width=3)
    elif kind == "doc":
        draw.rectangle((x + 8, y + 4, x + 34, y + 42), outline=c, width=3)
        for yy in [14, 24, 34]:
            draw.line((x + 14, y + yy, x + 28, y + yy), fill=c, width=2)
    elif kind == "target":
        draw.ellipse((x + 5, y + 5, x + 39, y + 39), outline=c, width=3)
        draw.ellipse((x + 14, y + 14, x + 30, y + 30), outline=c, width=3)
        draw.line((x + 22, y, x + 22, y + 44), fill=c, width=2)
        draw.line((x, y + 22, x + 44, y + 22), fill=c, width=2)
    elif kind == "brain":
        draw.ellipse((x + 4, y + 10, x + 40, y + 36), outline=c, width=3)
        draw.arc((x + 8, y + 12, x + 25, y + 34), 90, 270, fill=c, width=2)
        draw.arc((x + 20, y + 12, x + 36, y + 34), -90, 90, fill=c, width=2)
    elif kind == "filter":
        draw.polygon([(x + 4, y + 6), (x + 40, y + 6), (x + 26, y + 24), (x + 26, y + 42), (x + 18, y + 42), (x + 18, y + 24)], outline=c)
        draw.line((x + 4, y + 6, x + 40, y + 6, x + 26, y + 24, x + 26, y + 42, x + 18, y + 42, x + 18, y + 24, x + 4, y + 6), fill=c, width=3)
    elif kind == "flag":
        draw.line((x + 8, y + 8, x + 8, y + 42), fill=c, width=3)
        draw.polygon([(x + 8, y + 8), (x + 35, y + 12), (x + 20, y + 22), (x + 8, y + 20)], outline=c)
    elif kind == "flow":
        draw.rectangle((x + 17, y + 4, x + 29, y + 16), outline=c, width=3)
        draw.rectangle((x + 4, y + 30, x + 16, y + 42), outline=c, width=3)
        draw.rectangle((x + 32, y + 30, x + 44, y + 42), outline=c, width=3)
        draw.line((x + 23, y + 16, x + 23, y + 25), fill=c, width=3)
        draw.line((x + 10, y + 25, x + 38, y + 25), fill=c, width=3)
        draw.line((x + 10, y + 25, x + 10, y + 30), fill=c, width=3)
        draw.line((x + 38, y + 25, x + 38, y + 30), fill=c, width=3)
    elif kind == "clipboard":
        draw.rounded_rectangle((x + 8, y + 8, x + 36, y + 42), radius=4, outline=c, width=3)
        draw.rounded_rectangle((x + 15, y + 3, x + 29, y + 13), radius=3, outline=c, width=2)
    elif kind == "refresh":
        draw.arc((x + 4, y + 8, x + 40, y + 40), 30, 310, fill=c, width=3)
        draw.polygon([(x + 37, y + 10), (x + 43, y + 22), (x + 30, y + 20)], fill=c)
    elif kind == "wrench":
        draw.line((x + 10, y + 36, x + 34, y + 12), fill=c, width=4)
        draw.ellipse((x + 28, y + 4, x + 42, y + 18), outline=c, width=3)
    elif kind == "code":
        draw.line((x + 14, y + 14, x + 4, y + 24), fill=c, width=3)
        draw.line((x + 4, y + 24, x + 14, y + 34), fill=c, width=3)
        draw.line((x + 30, y + 14, x + 40, y + 24), fill=c, width=3)
        draw.line((x + 40, y + 24, x + 30, y + 34), fill=c, width=3)
    elif kind == "search":
        draw.ellipse((x + 5, y + 5, x + 30, y + 30), outline=c, width=3)
        draw.line((x + 27, y + 27, x + 42, y + 42), fill=c, width=3)
    elif kind == "db":
        draw.ellipse((x + 6, y + 6, x + 40, y + 18), outline=c, width=3)
        draw.line((x + 6, y + 12, x + 6, y + 36), fill=c, width=3)
        draw.line((x + 40, y + 12, x + 40, y + 36), fill=c, width=3)
        draw.ellipse((x + 6, y + 30, x + 40, y + 42), outline=c, width=3)
    elif kind == "book":
        draw.rectangle((x + 5, y + 8, x + 22, y + 40), outline=c, width=3)
        draw.rectangle((x + 22, y + 8, x + 39, y + 40), outline=c, width=3)
    elif kind == "shield":
        draw.polygon([(x + 22, y + 4), (x + 40, y + 12), (x + 36, y + 34), (x + 22, y + 44), (x + 8, y + 34), (x + 4, y + 12)], outline=c)
        draw.line((x + 22, y + 4, x + 40, y + 12, x + 36, y + 34, x + 22, y + 44, x + 8, y + 34, x + 4, y + 12, x + 22, y + 4), fill=c, width=3)
    elif kind == "chart":
        for i, h in enumerate([14, 24, 34]):
            draw.rectangle((x + 6 + i * 12, y + 42 - h, x + 14 + i * 12, y + 42), outline=c, width=3)


def feature_card(draw, xy, kind: str, title: str, subtitle: str, color: str):
    box(draw, xy, "", "gray2", color, "body", radius=10)
    x1, y1, x2, y2 = xy
    icon(draw, kind, x1 + 18, y1 + 18, color)
    draw.text((x1 + 72, y1 + 24), title, font=FONT["body"], fill=COLOR["text"])
    draw.text((x1 + 72, y1 + 50), subtitle, font=FONT["small"], fill=COLOR["muted"])


def draw_architecture():
    """Draw the main architecture in an enterprise agent-platform style."""
    image, draw = new_canvas(
        1800,
        1150,
        "Superset Agent Service 架构图",
        "MCP-enabled Agent Sidecar Architecture · Agent + RAG · Plan + ReAct + Reflection Hybrid Workflow",
    )

    # Left user/system side panel.
    box(draw, (35, 135, 260, 650), "", "purple2", "purple", radius=14)
    draw.text((72, 165), "用户 / 外部系统", font=FONT["h2"], fill=COLOR["text"])
    for y, kind, title, sub in [
        (235, "user", "用户", "User"),
        (340, "chat", "对话界面", "Web / App"),
        (445, "api", "命令行 / API", "CLI / SDK"),
        (550, "webhook", "Webhook", "事件触发"),
    ]:
        feature_card(draw, (58, y, 238, y + 82), kind, title, sub, "purple")

    # Central core.
    box(draw, (370, 70, 1295, 810), "", "blue2", "blue", radius=16)
    draw.text((795, 102), "AI Agent 核心 / Agent Core", font=FONT["h1"], fill=COLOR["text"])

    # Perception.
    box(draw, (405, 155, 1260, 295), "", "gray2", "blue", radius=16)
    draw.rounded_rectangle((405, 155, 1260, 295), radius=16, outline=COLOR["blue"], width=2)
    draw.text((760, 182), "感知与理解 / Perception & Understanding", font=FONT["h2"], fill=COLOR["blue"])
    for x, kind, title, sub in [
        (430, "doc", "输入解析", "Input Parsing"),
        (615, "target", "意图识别", "Intent Detection"),
        (800, "brain", "上下文理解", "Context Understanding"),
        (985, "filter", "信息抽取", "Information Extraction"),
    ]:
        feature_card(draw, (x, 215, x + 165, 272), kind, title, sub, "blue")

    # Planning.
    box(draw, (405, 345, 1260, 495), "", "green2", "green", radius=16)
    draw.text((765, 372), "决策与规划 / Decision & Planning", font=FONT["h2"], fill=COLOR["green"])
    for x, kind, title, sub in [
        (430, "flag", "目标理解", "Goal Understanding"),
        (635, "flow", "任务分解", "Task Decomposition"),
        (840, "clipboard", "计划生成", "Plan Generation"),
        (1045, "refresh", "自我反思", "Reflection"),
    ]:
        feature_card(draw, (x, 405, x + 165, 468), kind, title, sub, "green")
        if x < 1045:
            arrow(draw, (x + 165, 436), (x + 200, 436), "gray", width=2)

    # Action.
    box(draw, (405, 530, 1260, 645), "", "orange2", "orange", radius=16)
    draw.text((780, 556), "行动执行 / Action Execution", font=FONT["h2"], fill=COLOR["orange"])
    for x, kind, title, sub in [
        (430, "wrench", "工具调用", "Tool Use"),
        (645, "code", "代码执行", "Code Execution"),
        (860, "search", "检索查询", "RAG Search"),
        (1075, "chat", "生成回复", "Final Response"),
    ]:
        feature_card(draw, (x, 585, x + 165, 625), kind, title, sub, "orange")

    # Memory.
    box(draw, (405, 690, 1260, 780), "", "purple2", "purple", radius=16)
    draw.text((780, 716), "记忆系统 / Memory & Knowledge", font=FONT["h2"], fill=COLOR["purple"])
    for x, kind, title, sub in [
        (430, "chat", "短期记忆", "Session Memory"),
        (625, "db", "长期记忆", "Long-term Memory"),
        (820, "book", "知识库", "Knowledge Base"),
        (1015, "target", "经验记忆", "Experience"),
    ]:
        feature_card(draw, (x, 735, x + 170, 765), kind, title, sub, "purple")

    # Right tools/services.
    box(draw, (1370, 110, 1760, 810), "", "green2", "green", radius=16)
    draw.text((1505, 150), "外部工具与服务", font=FONT["h2"], fill=COLOR["green"])
    draw.text((1505, 176), "External Tools & Services", font=FONT["body"], fill=COLOR["muted"])
    sections = [
        (220, "工具 / Tools", [("wrench", "Superset MCP"), ("shield", "SQL Guard"), ("refresh", "Policy Guard"), ("chat", "Custom Tools")]),
        (390, "数据与 API / Data & API", [("db", "业务数据库"), ("api", "Superset API"), ("target", "Metadata"), ("chat", "Legacy API")]),
        (560, "检索与知识 / Retrieval", [("search", "RAG Retriever"), ("book", "文档库"), ("db", "Vector DB"), ("filter", "Reranker")]),
    ]
    for y, title, cards in sections:
        box(draw, (1400, y, 1730, y + 135), "", "green2", "green", radius=12)
        draw.text((1425, y + 22), title, font=FONT["body"], fill=COLOR["green"])
        cx = 1425
        for kind, text in cards:
            icon(draw, kind, cx, y + 58, "green")
            draw.text((cx - 4, y + 105), text, font=FONT["tiny"], fill=COLOR["text"])
            cx += 78

    # Model layer.
    box(draw, (300, 850, 1390, 950), "", "blue2", "blue", radius=14)
    draw.text((720, 878), "模型层 / Model Layer", font=FONT["h2"], fill=COLOR["blue"])
    for x, kind, title, sub in [
        (380, "brain", "大语言模型", "LLM"),
        (590, "db", "嵌入模型", "Embedding"),
        (790, "filter", "重排模型", "Reranker"),
        (990, "doc", "多模态模型", "Multimodal"),
    ]:
        feature_card(draw, (x, 895, x + 165, 932), kind, title, sub, "blue")

    # Bottom infra and observability.
    box(draw, (50, 990, 1130, 1120), "", "gray2", "gray", radius=14)
    draw.text((510, 1020), "基础设施与支撑 / Infrastructure & Support", font=FONT["h2"], fill=COLOR["text"])
    for x, kind, title in [
        (105, "db", "向量数据库"),
        (235, "db", "关系数据库"),
        (365, "doc", "对象存储"),
        (495, "db", "缓存 Redis"),
        (625, "chat", "消息队列"),
        (755, "doc", "日志存储"),
        (885, "shield", "权限安全"),
    ]:
        icon(draw, kind, x, 1050, "gray")
        draw.text((x - 10, 1100), title, font=FONT["small"], fill=COLOR["text"])

    box(draw, (1160, 990, 1760, 1120), "", "gray2", "gray", radius=14)
    draw.text((1390, 1020), "观测与评估 / Observability & Evaluation", font=FONT["h2"], fill=COLOR["text"])
    for x, kind, title in [(1215, "chart", "日志追踪"), (1350, "chart", "性能监控"), (1485, "clipboard", "评估指标"), (1620, "refresh", "反馈优化")]:
        icon(draw, kind, x, 1050, "gray")
        draw.text((x - 8, 1100), title, font=FONT["small"], fill=COLOR["text"])

    # Arrows.
    arrow(draw, (260, 355), (370, 355), "gray", width=3)
    arrow(draw, (370, 455), (260, 455), "gray", width=3)
    arrow(draw, (825, 295), (825, 345), "gray", width=3)
    arrow(draw, (825, 495), (825, 530), "gray", width=3)
    arrow(draw, (825, 645), (825, 690), "gray", width=3)
    arrow(draw, (1295, 505), (1370, 505), "gray", width=3)
    arrow(draw, (845, 810), (845, 850), "gray", width=3)
    arrow(draw, (1565, 810), (1565, 990), "gray", width=2)
    save(image, "architecture-agent-rag.png")


def main():
    draw_architecture()
    draw_workflow()
    draw_skills()
    draw_modules()
    draw_data_model()
    draw_deployment()
    draw_governance()
    draw_observability()
    draw_roadmap()


if __name__ == "__main__":
    main()
