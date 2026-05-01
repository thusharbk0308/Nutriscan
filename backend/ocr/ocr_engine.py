import easyocr

# Initialize once (important for performance)
reader = easyocr.Reader(['en'])

def extract_text(image_path):
    results = reader.readtext(image_path, detail=0)
    return "\n".join(results)
