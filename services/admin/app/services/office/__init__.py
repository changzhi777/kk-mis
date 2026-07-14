"""office 桥服务 — admin 调用 oa-agent 的文档处理工具（绕过 LLM）。

oa-agent 暴露 GET /tools（列工具）+ POST /tools/{name}（直接调用），
本子包封装 httpx 调用，供 routes/office.py 使用。office 场景（OA 附件解析、
CMS 导出）通过本桥复用 oa-agent 的 read_docx/read_pdf/excel_read/write_docx 等能力，
不在 admin 重复造文档处理轮子。
"""

from . import bridge

__all__ = ["bridge"]
