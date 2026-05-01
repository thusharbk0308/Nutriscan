from ocr.ocr_engine import extract_text
from nlp.extractor import extract_nutrition
from nlp.normalizer import normalize_to_100g

def main():
    image_path = "data/sample_images/maxresdefault.jpg"

    # Step 1: OCR
    text = extract_text(image_path)

    # Step 2: CLEAN OCR TEXT (after extraction)
    text = text.replace("Omg", "0mg")
    text = text.replace("Og", "0g")
    text = text.replace("O%", "0%")

    print("RAW TEXT:\n")
    print(text)

    # Step 3: Extract
    nutrition = extract_nutrition(text)
    print("\nEXTRACTED:\n", nutrition)

    # Step 4: Normalize
    normalized = normalize_to_100g(nutrition)
    print("\nNORMALIZED (per 100g):\n", normalized)


if __name__ == "__main__":
    main()