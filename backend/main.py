from ocr.ocr_engine import extract_text
from nlp.extractor import extract_nutrition
from nlp.normalizer import normalize_to_100g
from utils.helpers import clean_ocr_text


def main():
    image_path = "data/sample_images/nutrition_label3.png"

    # Step 1: OCR
    text = extract_text(image_path)

    # Step 2: CLEAN OCR TEXT (use helper)
    text = clean_ocr_text(text)

    print("RAW TEXT:\n")
    print(text)

    # Step 3: Extract
    nutrition = extract_nutrition(text)
    print("\nEXTRACTED:\n", nutrition)

    # Step 4: Normalize
    normalized = normalize_to_100g(nutrition)
    print("\nNORMALIZED (per 100g):\n", normalized)

    # Step 5: Confidence warning (optional but useful)
    if len(nutrition) < 3:
        print("\n⚠️ Low confidence OCR result — try better crop")


if __name__ == "__main__":
    main()