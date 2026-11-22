"""Trợ lý LeadScan: chatbot hỏi đáp về hệ thống cho khách, thành viên và đối tác.

kb/*.md     kiến thức về hệ thống (viết tay, bám đúng code) — nạp vào system prompt theo đối tượng
tools.py    công cụ tra cứu số liệu sống (giá, thưởng, cơ hội đang bán, dữ liệu của chính người hỏi)
engine.py   vòng gọi AI có công cụ (DeepSeek / Cohere), giới hạn lượt, ghi log
"""
