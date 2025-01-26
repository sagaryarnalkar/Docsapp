from docling.models.tesseract_ocr_model import TesseractOcrModel
from docling.models.layout_model import LayoutModel
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Manually initialize models (modify paths if needed)
ocr_model = TesseractOcrModel(model_path="/home/sagary/docsapp/models/tesseract/")
layout_model = LayoutModel(model_path="/home/sagary/docsapp/models/layout/")

# Configure pipeline options
pipeline_options = PdfPipelineOptions(
    generate_page_images=False,  # Prevent unnecessary image processing
    extract_tables=True,  # Enable table extraction
    ocr_enabled=True  # Enable OCR if needed
)

# Initialize pipeline with correct options
pipeline = StandardPdfPipeline(pipeline_options)





def extract_text_from_file(file_path):
    """
    Extracts structured text from a document using Docling.
    Handles PDF, DOCX, and images with OCR.
    """
    try:
        with open(file_path, "rb") as file:
            extracted_text = pipeline.run(file)
        return extracted_text.strip()
    except Exception as e:
        print(f"Error extracting text: {e}")
        return None  # Fallback mechanism in case of failure
