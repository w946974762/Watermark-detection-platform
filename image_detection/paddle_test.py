import json
from paddleocr import PaddleOCR
def paddle_test(image_path):
    ocr = PaddleOCR(
        use_doc_orientation_classify=False, use_doc_unwarping=False,
        use_textline_orientation=False)
    result = ocr.predict(input=image_path)
    for res in result:
        json_path = "/seal_flask/image_detection/output/5_res.json"
        res.save_to_json(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            rec_texts = data.get("rec_texts", [])
            rec_boxes = data.get("rec_boxes", [])
            return rec_texts, rec_boxes