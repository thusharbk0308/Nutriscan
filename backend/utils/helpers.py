def clean_ocr_text(text):
    # Fix OCR misreads
    text = text.replace("Omg", "0mg")
    text = text.replace("Og", "0g")
    text = text.replace("O%", "0%")

    # Fix words
    text = text.replace("Calores", "Calories")
    text = text.replace("Calones", "Calories")

    return text