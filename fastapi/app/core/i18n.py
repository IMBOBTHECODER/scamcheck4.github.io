"""Minimal UI string tables for the supported languages.

`strings(language)` returns the table for that language (Vietnamese fallback).
Only UI chrome is translated here; the scam-check verdict text comes from the
model in Vietnamese.
"""

DEFAULT_LANG = "vi"

STRINGS = {
    "vi": {
        # nav
        "nav_home": "Trang chủ",
        "nav_history": "Lịch sử",
        "nav_settings": "Cài đặt",
        # history
        "history_heading": "Lịch sử kiểm tra",
        "no_history": "Chưa có lượt kiểm tra nào.",
        "clear_history": "Xóa lịch sử",
        # home / checker
        "index_heading": "Kiểm tra lừa đảo",
        "index_intro": "Dán một tin nhắn hoặc đường dẫn bên dưới để kiểm tra.",
        "placeholder": "Dán nội dung cần kiểm tra...",
        "check_button": "Kiểm tra",
        "signals_heading": "Dấu hiệu",
        "actions_heading": "Hành động đề xuất",
        "no_signals": "Không phát hiện dấu hiệu đáng ngờ.",
        "err_empty": "Vui lòng nhập nội dung cần kiểm tra.",
        "err_too_long": "Nội dung quá dài (tối đa {max} ký tự).",
        # settings
        "settings_heading": "Cài đặt",
        "theme_label": "Giao diện",
        "theme_dark": "Tối",
        "theme_light": "Sáng",
        "theme_auto": "Tự động (theo hệ thống)",
        "language_label": "Ngôn ngữ",
        "lang_vi": "Tiếng Việt",
        "lang_en": "English",
        "save_button": "Lưu cài đặt",
        "saved_message": "Đã lưu cài đặt.",
        "specs_heading": "Thông tin hệ thống",
        "version_label": "Phiên bản",
        "max_length_label": "Độ dài tối đa (ký tự)",
        "language_name": "Ngôn ngữ",
    },
    "en": {
        "nav_home": "Home",
        "nav_history": "History",
        "nav_settings": "Settings",
        "history_heading": "Check history",
        "no_history": "No checks yet.",
        "clear_history": "Clear history",
        "index_heading": "Scam Check",
        "index_intro": "Paste a message or link below to check it.",
        "placeholder": "Paste the content to check...",
        "check_button": "Check",
        "signals_heading": "Indicators",
        "actions_heading": "Suggested actions",
        "no_signals": "No suspicious indicators found.",
        "err_empty": "Please enter something to check.",
        "err_too_long": "Content is too long (max {max} characters).",
        "settings_heading": "Settings",
        "theme_label": "Appearance",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "theme_auto": "Auto (system)",
        "language_label": "Language",
        "lang_vi": "Tiếng Việt",
        "lang_en": "English",
        "save_button": "Save settings",
        "saved_message": "Settings saved.",
        "specs_heading": "System info",
        "version_label": "Version",
        "max_length_label": "Max length (characters)",
        "language_name": "Language",
    },
}


def strings(language):
    """Return the string table for `language`, falling back to Vietnamese."""
    return STRINGS.get(language, STRINGS[DEFAULT_LANG])
