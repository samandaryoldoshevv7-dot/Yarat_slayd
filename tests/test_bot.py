"""Bot xabarlari: AI va foydalanuvchi matni Telegram HTML'ini buzmasligi kerak."""
import bot


def test_plan_text_escapes_html():
    text = bot.plan_text({"outline": {"title": "C++ & <Python>", "subtitle": "a<b", "slides": ["<script>", "x & y"]},
                          "slides": 7, "lang": "uz"})
    assert "<Python>" not in text and "<script>" not in text and "a<b" not in text
    assert "&lt;Python&gt;" in text and "x &amp; y" in text
