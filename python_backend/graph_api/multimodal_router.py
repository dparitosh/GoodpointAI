"""
 Multi-Modal Data Understanding Service
=========================================

Parse and extract data from multiple file formats:
- PDFs (text + images)
- Images (OCR + vision analysis)
- CAD files (metadata extraction)
- Excel files (structured data)
- Word documents
- Videos (frame analysis)

Integrations:
- Ollama vision models (LLaVA, BakLLaVA)
- PyMuPDF for PDF processing
- pytesseract for OCR
- OpenCV for image processing
- openpyxl for Excel files
- python-docx for Word files
"""

import logging
import os
import base64
import io
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, BinaryIO
from enum import Enum
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/multimodal", tags=["Multi-Modal Understanding"])


# ============= MODELS =============

class FileType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    CAD = "cad"
    EXCEL = "excel"
    WORD = "word"
    VIDEO = "video"
    UNKNOWN = "unknown"


class ExtractionMethod(str, Enum):
    OCR = "ocr"
    VISION_LLM = "vision_llm"
    TEXT_PARSER = "text_parser"
    METADATA = "metadata"
    HYBRID = "hybrid"


class FileAnalysisRequest(BaseModel):
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    extraction_method: ExtractionMethod = ExtractionMethod.HYBRID
    vision_model: str = "llava:latest"
    extract_metadata: bool = True
    extract_text: bool = True
    extract_images: bool = False
    ocr_language: str = "eng"


class FileAnalysisResponse(BaseModel):
    file_name: str
    file_type: FileType
    file_size_bytes: int
    extraction_method: ExtractionMethod
    text_content: Optional[str] = None
    metadata: Dict[str, Any] = {}
    extracted_data: Dict[str, Any] = {}
    images_analyzed: int = 0
    processing_time_ms: int = 0
    success: bool = True
    error: Optional[str] = None


class ImageAnalysisRequest(BaseModel):
    image_base64: str
    prompt: str = "Describe this image in detail, focusing on technical specifications, dimensions, and any text visible."
    vision_model: str = "llava:latest"


class ImageAnalysisResponse(BaseModel):
    description: str
    extracted_text: Optional[str] = None
    metadata: Dict[str, Any] = {}
    confidence: float = 0.0


# ============= MULTI-MODAL SERVICE =============

class MultiModalService:
    """Service for analyzing multiple file formats using AI"""
    
    def __init__(self):
        self.supported_image_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        self.supported_pdf_formats = {'.pdf'}
        self.supported_cad_formats = {'.dwg', '.dxf', '.step', '.stp', '.iges', '.igs'}
        self.supported_excel_formats = {'.xlsx', '.xls', '.xlsm', '.csv'}
        self.supported_word_formats = {'.docx', '.doc'}
        self.supported_video_formats = {'.mp4', '.avi', '.mov', '.mkv'}
    
    def detect_file_type(self, filename: str) -> FileType:
        """Detect file type from extension"""
        ext = Path(filename).suffix.lower()
        
        if ext in self.supported_image_formats:
            return FileType.IMAGE
        elif ext in self.supported_pdf_formats:
            return FileType.PDF
        elif ext in self.supported_cad_formats:
            return FileType.CAD
        elif ext in self.supported_excel_formats:
            return FileType.EXCEL
        elif ext in self.supported_word_formats:
            return FileType.WORD
        elif ext in self.supported_video_formats:
            return FileType.VIDEO
        else:
            return FileType.UNKNOWN
    
    async def analyze_with_vision_llm(
        self,
        image_data: bytes,
        prompt: str,
        model: str = "llava:latest"
    ) -> Dict[str, Any]:
        """Analyze image using Ollama vision model"""
        try:
            import ollama
            
            # Encode image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Call Ollama vision model
            response = ollama.chat(
                model=model,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [image_base64]
                }]
            )
            
            return {
                "description": response['message']['content'],
                "model": model,
                "success": True
            }
            
        except ImportError:
            logger.warning("Ollama not installed, falling back to basic analysis")
            return {
                "description": "Vision analysis not available (Ollama not installed)",
                "model": model,
                "success": False
            }
        except Exception as e:
            logger.error(f"Error in vision LLM analysis: {e}")
            return {
                "description": f"Error: {str(e)}",
                "model": model,
                "success": False
            }
    
    async def extract_text_from_pdf(self, file_content: bytes) -> Dict[str, Any]:
        """Extract text and images from PDF"""
        try:
            import fitz  # PyMuPDF
            
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            
            text_content = []
            images = []
            metadata = {
                "page_count": len(pdf_document),
                "metadata": pdf_document.metadata
            }
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Extract text
                text = page.get_text()
                if text.strip():
                    text_content.append(f"--- Page {page_num + 1} ---\n{text}")
                
                # Extract images
                image_list = page.get_images()
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    images.append({
                        "page": page_num + 1,
                        "index": img_index,
                        "image_bytes": base_image["image"]
                    })
            
            pdf_document.close()
            
            return {
                "text": "\n\n".join(text_content),
                "images": images,
                "metadata": metadata,
                "success": True
            }
            
        except ImportError:
            logger.warning("PyMuPDF not installed")
            return {
                "text": "",
                "images": [],
                "metadata": {},
                "success": False,
                "error": "PyMuPDF not installed"
            }
        except Exception as e:
            logger.error(f"Error extracting PDF: {e}")
            return {
                "text": "",
                "images": [],
                "metadata": {},
                "success": False,
                "error": str(e)
            }
    
    async def ocr_image(self, image_data: bytes, language: str = "eng") -> str:
        """Perform OCR on image"""
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image, lang=language)
            
            return text.strip()
            
        except ImportError:
            logger.warning("pytesseract not installed")
            return ""
        except Exception as e:
            logger.error(f"Error in OCR: {e}")
            return ""
    
    async def extract_excel_data(self, file_content: bytes) -> Dict[str, Any]:
        """Extract data from Excel file"""
        try:
            import openpyxl
            
            workbook = openpyxl.load_workbook(io.BytesIO(file_content))
            
            sheets_data = {}
            metadata = {
                "sheet_count": len(workbook.sheetnames),
                "sheet_names": workbook.sheetnames
            }
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                
                # Get dimensions
                max_row = sheet.max_row
                max_col = sheet.max_column
                
                # Extract data (limit to first 100 rows for performance)
                rows_data = []
                for row in sheet.iter_rows(max_row=min(max_row, 100), values_only=True):
                    rows_data.append(list(row))
                
                sheets_data[sheet_name] = {
                    "dimensions": {"rows": max_row, "columns": max_col},
                    "data": rows_data[:100],  # First 100 rows
                    "truncated": max_row > 100
                }
            
            return {
                "sheets": sheets_data,
                "metadata": metadata,
                "success": True
            }
            
        except ImportError:
            logger.warning("openpyxl not installed")
            return {
                "sheets": {},
                "metadata": {},
                "success": False,
                "error": "openpyxl not installed"
            }
        except Exception as e:
            logger.error(f"Error extracting Excel: {e}")
            return {
                "sheets": {},
                "metadata": {},
                "success": False,
                "error": str(e)
            }
    
    async def extract_word_data(self, file_content: bytes) -> Dict[str, Any]:
        """Extract text from Word document"""
        try:
            from docx import Document
            
            doc = Document(io.BytesIO(file_content))
            
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            tables_data = []
            
            for table in doc.tables:
                table_data = []
                for row in table.rows:
                    row_data = [cell.text for cell in row.cells]
                    table_data.append(row_data)
                tables_data.append(table_data)
            
            metadata = {
                "paragraph_count": len(paragraphs),
                "table_count": len(tables_data)
            }
            
            return {
                "text": "\n\n".join(paragraphs),
                "tables": tables_data,
                "metadata": metadata,
                "success": True
            }
            
        except ImportError:
            logger.warning("python-docx not installed")
            return {
                "text": "",
                "tables": [],
                "metadata": {},
                "success": False,
                "error": "python-docx not installed"
            }
        except Exception as e:
            logger.error(f"Error extracting Word: {e}")
            return {
                "text": "",
                "tables": [],
                "metadata": {},
                "success": False,
                "error": str(e)
            }
    
    async def analyze_file(
        self,
        file_content: bytes,
        filename: str,
        extraction_method: ExtractionMethod,
        vision_model: str,
        extract_metadata: bool,
        extract_text: bool,
        extract_images: bool,
        ocr_language: str
    ) -> FileAnalysisResponse:
        """Analyze file with specified extraction method"""
        start_time = datetime.now(timezone.utc)
        
        file_type = self.detect_file_type(filename)
        file_size = len(file_content)
        
        result = FileAnalysisResponse(
            file_name=filename,
            file_type=file_type,
            file_size_bytes=file_size,
            extraction_method=extraction_method
        )
        
        try:
            # PDF processing
            if file_type == FileType.PDF:
                pdf_data = await self.extract_text_from_pdf(file_content)
                
                if pdf_data["success"]:
                    result.text_content = pdf_data["text"]
                    result.metadata = pdf_data["metadata"]
                    
                    # Analyze images with vision LLM if requested
                    if extract_images and extraction_method in [ExtractionMethod.VISION_LLM, ExtractionMethod.HYBRID]:
                        for img_info in pdf_data["images"][:5]:  # Limit to 5 images
                            vision_result = await self.analyze_with_vision_llm(
                                img_info["image_bytes"],
                                "Describe this technical diagram or image. Extract any text, dimensions, or specifications visible.",
                                vision_model
                            )
                            
                            if vision_result["success"]:
                                result.extracted_data[f"image_page_{img_info['page']}_index_{img_info['index']}"] = vision_result["description"]
                                result.images_analyzed += 1
                else:
                    result.error = pdf_data.get("error")
            
            # Image processing
            elif file_type == FileType.IMAGE:
                if extraction_method in [ExtractionMethod.VISION_LLM, ExtractionMethod.HYBRID]:
                    vision_result = await self.analyze_with_vision_llm(
                        file_content,
                        "Describe this image in detail. Extract any text, technical specifications, or structured data visible.",
                        vision_model
                    )
                    
                    if vision_result["success"]:
                        result.text_content = vision_result["description"]
                        result.images_analyzed = 1
                
                if extraction_method in [ExtractionMethod.OCR, ExtractionMethod.HYBRID]:
                    ocr_text = await self.ocr_image(file_content, ocr_language)
                    if ocr_text:
                        result.extracted_data["ocr_text"] = ocr_text
            
            # Excel processing
            elif file_type == FileType.EXCEL:
                excel_data = await self.extract_excel_data(file_content)
                
                if excel_data["success"]:
                    result.extracted_data = excel_data["sheets"]
                    result.metadata = excel_data["metadata"]
                else:
                    result.error = excel_data.get("error")
            
            # Word processing
            elif file_type == FileType.WORD:
                word_data = await self.extract_word_data(file_content)
                
                if word_data["success"]:
                    result.text_content = word_data["text"]
                    result.extracted_data["tables"] = word_data["tables"]
                    result.metadata = word_data["metadata"]
                else:
                    result.error = word_data.get("error")
            
            # CAD files (placeholder for future implementation)
            elif file_type == FileType.CAD:
                result.error = "CAD file processing not yet implemented"
                result.success = False
            
            else:
                result.error = f"Unsupported file type: {file_type}"
                result.success = False
            
        except Exception as e:
            logger.error(f"Error analyzing file {filename}: {e}")
            result.error = str(e)
            result.success = False
        
        # Calculate processing time
        end_time = datetime.now(timezone.utc)
        result.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return result


# Global service instance
service = MultiModalService()


# ============= API ENDPOINTS =============

@router.post("/analyze-file", summary="Analyze File with Multi-Modal AI")
async def analyze_file(
    file: UploadFile = File(...),
    extraction_method: ExtractionMethod = ExtractionMethod.HYBRID,
    vision_model: str = "llava:latest",
    extract_metadata: bool = True,
    extract_text: bool = True,
    extract_images: bool = False,
    ocr_language: str = "eng"
):
    """
    Analyze uploaded file using multi-modal AI
    
    Supported formats:
    - PDF: Text extraction + vision analysis of embedded images
    - Images: Vision LLM + OCR
    - Excel: Structured data extraction
    - Word: Text + tables extraction
    - CAD: Metadata extraction (coming soon)
    """
    try:
        # Read file content
        file_content = await file.read()
        
        # Analyze file
        result = await service.analyze_file(
            file_content=file_content,
            filename=file.filename,
            extraction_method=extraction_method,
            vision_model=vision_model,
            extract_metadata=extract_metadata,
            extract_text=extract_text,
            extract_images=extract_images,
            ocr_language=ocr_language
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in file analysis endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-image", summary="Analyze Image with Vision LLM")
async def analyze_image(request: ImageAnalysisRequest):
    """Analyze image using Ollama vision model (LLaVA, BakLLaVA)"""
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.image_base64)
        
        # Analyze with vision LLM
        vision_result = await service.analyze_with_vision_llm(
            image_data=image_data,
            prompt=request.prompt,
            model=request.vision_model
        )
        
        # Optional: Run OCR
        ocr_text = await service.ocr_image(image_data)
        
        return ImageAnalysisResponse(
            description=vision_result["description"],
            extracted_text=ocr_text if ocr_text else None,
            metadata={"model": vision_result["model"]},
            confidence=1.0 if vision_result["success"] else 0.0
        )
        
    except Exception as e:
        logger.error(f"Error in image analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-formats", summary="Get Supported File Formats")
async def get_supported_formats():
    """Get list of supported file formats"""
    return {
        "images": list(service.supported_image_formats),
        "pdf": list(service.supported_pdf_formats),
        "cad": list(service.supported_cad_formats),
        "excel": list(service.supported_excel_formats),
        "word": list(service.supported_word_formats),
        "video": list(service.supported_video_formats)
    }


@router.get("/vision-models", summary="Get Available Vision Models")
async def get_vision_models():
    """Get list of available Ollama vision models"""
    try:
        import ollama
        
        models = ollama.list()
        vision_models = [
            model for model in models.get('models', [])
            if 'llava' in model['name'].lower() or 'bakllava' in model['name'].lower()
        ]
        
        return {
            "available_models": [model['name'] for model in vision_models],
            "recommended": "llava:latest"
        }
        
    except ImportError:
        return {
            "available_models": [],
            "recommended": "llava:latest",
            "error": "Ollama not installed"
        }
    except Exception as e:
        logger.error(f"Error listing vision models: {e}")
        return {
            "available_models": [],
            "recommended": "llava:latest",
            "error": str(e)
        }
