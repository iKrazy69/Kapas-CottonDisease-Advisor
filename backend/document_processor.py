"""
============================================
DOCUMENT PROCESSOR MODULE
VB-GRAMG Government Documents RAG System
============================================

Handles:
- PDF text extraction
- DOCX text extraction
- Plain text file processing
- Intelligent text chunking with overlap
- Metadata extraction
"""

import os
import sys
import logging
import re
from typing import List, Tuple, Dict, Optional
from pathlib import Path

from PyPDF2 import PdfReader
from docx import Document as DocxDocument

from config import Config

# ============================================
# LOGGING
# ============================================

logger = logging.getLogger(__name__)

# ============================================
# DOCUMENT PROCESSOR CLASS
# ============================================

import unicodedata

# pdftotext writes Symbol-font glyphs as private-use characters: U+F000 + the ASCII code of the glyph
# (U+F02D is a hyphen between the numbers in "25-30 g", U+F020 a space, U+F0B7 a bullet).
_SYMBOL_FONT_SPECIAL = {0xF0B7: ' ', 0xF0A7: ' ', 0xF0D8: ' ', 0xF0AE: ' '}   # bullets / arrows: layout only
_KEEP_FORMAT_CHARS = {'\u200c', '\u200d'}                                          # joiners that Devanagari needs


def clean_characters(text: str) -> str:
    """Normalise Symbol-font private-use characters, drop unreadable ones, keep every real character."""
    out = []
    for ch in text:
        code = ord(ch)
        if 0xF020 <= code <= 0xF07E:
            out.append(chr(code - 0xF000))
        elif code in _SYMBOL_FONT_SPECIAL:
            out.append(_SYMBOL_FONT_SPECIAL[code])
        elif ch in '\n\t ':
            out.append(ch)
        else:
            cat = unicodedata.category(ch)
            if cat in ('Cc', 'Co', 'Cs', 'Cn') or (cat == 'Cf' and ch not in _KEEP_FORMAT_CHARS):
                out.append(' ' if cat == 'Cc' else '')
            else:
                out.append(ch)
    return ''.join(out)


# A numbered heading written in capitals on a line of its own, such as "7. MYROTHECIUM LEAF SPOT".
_HEADING_LINE = re.compile(r"^[ \t]*\d{1,2}\.[ \t]+([A-Z][A-Z ,/()&'\-]{3,80}?)[ \t]*$", re.M)
_SECTION_MARK = re.compile(r'\[\[SECTION: (.*?)\]\]')


def mark_section_headings(text: str) -> str:
    """Replace each numbered all-capitals heading line by an inline marker that survives whitespace cleaning.
    Lines like "Economic threshold: 2-5%" repeat under every disease; without their heading a chunk cannot say
    which disease it is about, and search cannot tell them apart."""
    def mark(m):
        title = m.group(1).strip()
        letters = [c for c in title if c.isalpha()]
        if len(letters) < 4 or not all(c.isupper() for c in letters):
            return m.group(0)
        return '\n[[SECTION: ' + title.title() + ']]\n'
    return _HEADING_LINE.sub(mark, text)


class DocumentProcessor:
    """
    Process various document formats and prepare text for RAG system.
    
    Supports:
    - PDF files (.pdf)
    - Word documents (.docx, .doc via conversion)
    - Plain text files (.txt)
    """

    def __init__(self):
        """Initialize document processor"""
        logger.info('🚀 Initializing Document Processor...')
        
        # Configuration
        self.chunk_size = Config.CHUNK_SIZE
        self.chunk_overlap = Config.CHUNK_OVERLAP
        
        logger.info(f'⚙️  Chunk size: {self.chunk_size} characters')
        logger.info(f'⚙️  Chunk overlap: {self.chunk_overlap} characters')
        logger.info('✅ Document Processor initialized')

    # ========================================
    # MAIN PROCESSING METHODS
    # ========================================

    def process_document(self, filepath: str) -> List[str]:
        """
        Process a document and return text chunks
        
        Args:
            filepath: Path to document file
        
        Returns:
            List of text chunks
        """
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f'File not found: {filepath}')
            
            logger.info(f'📄 Processing document: {filepath}')
            
            # Get file extension
            file_ext = os.path.splitext(filepath)[1].lower()
            
            # Extract text based on file type
            if file_ext == '.pdf':
                text = self._extract_pdf(filepath)
            elif file_ext in ['.docx', '.doc']:
                text = self._extract_docx(filepath)
            elif file_ext == '.txt':
                text = self._extract_txt(filepath)
            else:
                raise ValueError(f'Unsupported file type: {file_ext}')
            
            if not text or len(text.strip()) == 0:
                logger.warning(f'⚠️  No text extracted from document: {filepath}')
                return []
            
            logger.info(f'✅ Text extracted ({len(text)} characters)')
            
            # Keep the headings: cleaning joins all lines, after which they can no longer be found
            text = mark_section_headings(text)
            
            # Clean text
            text = self._clean_text(text)
            logger.info(f'✅ Text cleaned ({len(text)} characters after cleaning)')
            
            # Chunk text (each chunk starts with the heading of the section it belongs to)
            chunks = self._chunk_sections(text)
            logger.info(f'✂️  Text split into {len(chunks)} chunks')
            
            return chunks
        
        except FileNotFoundError as e:
            logger.error(f'❌ File not found: {str(e)}')
            raise
        except ValueError as e:
            logger.error(f'❌ Invalid file type: {str(e)}')
            raise
        except Exception as e:
            logger.error(f'❌ Document processing failed: {str(e)}')
            raise

    # ========================================
    # TEXT EXTRACTION METHODS
    # ========================================

    def _extract_pdf(self, filepath: str) -> str:
        """
        Extract text from PDF file
        
        Args:
            filepath: Path to PDF file
        
        Returns:
            Extracted text
        """
        try:
            logger.info(f'📕 Extracting text from PDF: {filepath}')
            
            text_parts = []
            
            with open(filepath, 'rb') as file:
                pdf_reader = PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                logger.info(f'📊 PDF has {num_pages} pages')
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        page_text = page.extract_text()
                        
                        if page_text:
                            # Add page break marker
                            text_parts.append(f"\n--- Page {page_num} ---\n{page_text}")
                            logger.info(f'✅ Extracted page {page_num}/{num_pages}')
                        else:
                            logger.warning(f'⚠️  No text found on page {page_num}')
                    
                    except Exception as e:
                        logger.warning(f'⚠️  Failed to extract page {page_num}: {str(e)}')
                        continue
            
            if not text_parts:
                raise Exception('No text could be extracted from PDF')
            
            full_text = '\n'.join(text_parts)
            logger.info(f'✅ PDF extraction complete ({len(full_text)} characters)')
            
            return full_text
        
        except Exception as e:
            logger.error(f'❌ PDF extraction failed: {str(e)}')
            raise

    def _extract_docx(self, filepath: str) -> str:
        """
        Extract text from DOCX file
        
        Args:
            filepath: Path to DOCX file
        
        Returns:
            Extracted text
        """
        try:
            logger.info(f'📗 Extracting text from DOCX: {filepath}')
            
            text_parts = []
            
            doc = DocxDocument(filepath)
            num_paragraphs = len(doc.paragraphs)
            
            logger.info(f'📊 Document has {num_paragraphs} paragraphs')
            
            # Extract paragraphs
            for para_num, paragraph in enumerate(doc.paragraphs, 1):
                text = paragraph.text.strip()
                
                if text:
                    text_parts.append(text)
                    
                    if para_num % 10 == 0:
                        logger.info(f'✅ Extracted {para_num}/{num_paragraphs} paragraphs')
            
            # Extract tables if present
            if doc.tables:
                logger.info(f'📊 Document has {len(doc.tables)} tables')
                
                for table_num, table in enumerate(doc.tables, 1):
                    table_text = self._extract_table(table)
                    if table_text:
                        text_parts.append(f"\n[Table {table_num}]\n{table_text}")
                    
                    logger.info(f'✅ Extracted table {table_num}/{len(doc.tables)}')
            
            if not text_parts:
                raise Exception('No text could be extracted from DOCX')
            
            full_text = '\n'.join(text_parts)
            logger.info(f'✅ DOCX extraction complete ({len(full_text)} characters)')
            
            return full_text
        
        except Exception as e:
            logger.error(f'❌ DOCX extraction failed: {str(e)}')
            raise

    def _extract_txt(self, filepath: str) -> str:
        """
        Extract text from plain text file
        
        Args:
            filepath: Path to TXT file
        
        Returns:
            Extracted text
        """
        try:
            logger.info(f'📄 Extracting text from TXT: {filepath}')
            
            with open(filepath, 'r', encoding='utf-8') as file:
                text = file.read()
            
            if not text or len(text.strip()) == 0:
                raise Exception('TXT file is empty')
            
            logger.info(f'✅ TXT extraction complete ({len(text)} characters)')
            
            return text
        
        except UnicodeDecodeError:
            logger.warning('⚠️  UTF-8 decoding failed, trying with latin-1...')
            
            try:
                with open(filepath, 'r', encoding='latin-1') as file:
                    text = file.read()
                
                logger.info(f'✅ TXT extraction complete with latin-1 ({len(text)} characters)')
                return text
            
            except Exception as e:
                logger.error(f'❌ TXT extraction failed: {str(e)}')
                raise
        
        except Exception as e:
            logger.error(f'❌ TXT extraction failed: {str(e)}')
            raise

    # ========================================
    # TABLE EXTRACTION
    # ========================================

    def _extract_table(self, table) -> str:
        """
        Extract text from Word table
        
        Args:
            table: DOCX table object
        
        Returns:
            Table text
        """
        try:
            table_text = []
            
            for row in table.rows:
                row_text = ' | '.join([cell.text.strip() for cell in row.cells])
                table_text.append(row_text)
            
            return '\n'.join(table_text)
        
        except Exception as e:
            logger.warning(f'⚠️  Failed to extract table: {str(e)}')
            return ''

    # ========================================
    # TEXT CLEANING
    # ========================================

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text
        
        Args:
            text: Raw text
        
        Returns:
            Cleaned text
        """
        logger.info('🧹 Cleaning text...')
        
        try:
            # Remove multiple whitespaces
            text = re.sub(r'\s+', ' ', text)
            
            # Remove extra newlines but preserve some structure
            text = re.sub(r'\n\n+', '\n\n', text)
            
            # Fix the glyphs PDF tools emit for Symbol-font characters, and drop only characters
            # that can never be read (control and private-use). Everything else is kept:
            # % @ / + degree and rupee signs and Devanagari vowel signs all matter in dose
            # text and in Hindi documents. (The old pattern deleted them, so "@ 25-30 g" became "2530 g".)
            text = clean_characters(text)
            
            # Remove leading/trailing whitespace
            text = text.strip()
            
            # Normalize newlines
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            
            logger.info('✅ Text cleaning complete')
            
            return text
        
        except Exception as e:
            logger.warning(f'⚠️  Text cleaning issue: {str(e)}')
            return text

    # ========================================
    # TEXT CHUNKING
    # ========================================

    def _chunk_sections(self, text: str) -> List[str]:
        """Chunk each section on its own and start every chunk with "[Section title] "."""
        parts = _SECTION_MARK.split(text)          # [before, title1, body1, title2, body2, ...]
        chunks = []
        if parts[0].strip():
            chunks += self._chunk_text(parts[0].strip())
        for i in range(1, len(parts) - 1, 2):
            title, body = parts[i].strip(), parts[i + 1].strip()
            if not body:
                continue
            chunks += [f'[{title}] {c}' for c in self._chunk_text(body)]
        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Full text
        
        Returns:
            List of text chunks
        """
        try:
            logger.info(f'✂️  Chunking text (size: {self.chunk_size}, overlap: {self.chunk_overlap})...')
            
            chunks = []
            text_length = len(text)
            
            if text_length == 0:
                logger.warning('⚠️  Text is empty')
                return []
            
            # If text is smaller than chunk size, return as single chunk
            if text_length <= self.chunk_size:
                logger.info('📝 Text smaller than chunk size, returning as single chunk')
                return [text]
            
            # Create overlapping chunks
            start = 0
            chunk_count = 0
            
            while start < text_length:
                # Calculate end position
                end = start + self.chunk_size
                
                # If this is not the last chunk, try to break at sentence boundary
                if end < text_length:
                    # Look for sentence boundary within last 50 characters
                    search_end = min(end, text_length)
                    search_start = max(start + self.chunk_size - 50, start)
                    
                    # Try to find period, question mark, or exclamation
                    for i in range(search_end - 1, search_start - 1, -1):
                        if text[i] in '.!?\n':
                            end = i + 1
                            break
                
                # Extract chunk
                chunk = text[start:end].strip()
                
                if len(chunk) > 0:
                    chunks.append(chunk)
                    chunk_count += 1
                    
                    # Log progress
                    if chunk_count % 10 == 0:
                        logger.info(f'✂️  Created {chunk_count} chunks...')
                
                # Move to next chunk with overlap
                start = end - self.chunk_overlap
            
            logger.info(f'✅ Chunking complete: {len(chunks)} chunks created')
            
            # Validate chunks
            valid_chunks = [c for c in chunks if len(c.strip()) > 10]
            removed = len(chunks) - len(valid_chunks)
            
            if removed > 0:
                logger.info(f'🗑️  Removed {removed} chunks with less than 10 characters')
            
            return valid_chunks
        
        except Exception as e:
            logger.error(f'❌ Chunking failed: {str(e)}')
            raise

    # ========================================
    # UTILITY METHODS
    # ========================================

    def get_document_info(self, filepath: str) -> Dict[str, any]:
        """
        Get information about a document
        
        Args:
            filepath: Path to document
        
        Returns:
            Document metadata
        """
        try:
            file_stat = os.stat(filepath)
            filename = os.path.basename(filepath)
            file_ext = os.path.splitext(filename)[1].lower()
            
            info = {
                'filename': filename,
                'filepath': filepath,
                'file_type': file_ext[1:] if file_ext else 'unknown',
                'file_size': file_stat.st_size,
                'file_size_mb': file_stat.st_size / (1024 * 1024),
                'created_at': file_stat.st_ctime,
                'modified_at': file_stat.st_mtime
            }
            
            logger.info(f'📋 Document info: {info}')
            
            return info
        
        except Exception as e:
            logger.error(f'❌ Failed to get document info: {str(e)}')
            return {}

    def validate_file(self, filepath: str) -> Tuple[bool, str]:
        """
        Validate if file can be processed
        
        Args:
            filepath: Path to file
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if file exists
            if not os.path.exists(filepath):
                return False, 'File does not exist'
            
            # Check if file is readable
            if not os.access(filepath, os.R_OK):
                return False, 'File is not readable'
            
            # Check file size (max 50MB)
            file_size = os.path.getsize(filepath)
            max_size = 50 * 1024 * 1024  # 50MB
            
            if file_size > max_size:
                return False, f'File is too large ({file_size / (1024*1024):.1f}MB > 50MB)'
            
            # Check file extension
            file_ext = os.path.splitext(filepath)[1].lower()
            allowed_extensions = {'.pdf', '.txt', '.docx', '.doc'}
            
            if file_ext not in allowed_extensions:
                return False, f'File type not supported: {file_ext}'
            
            logger.info(f'✅ File validation passed: {filepath}')
            
            return True, 'File is valid'
        
        except Exception as e:
            logger.error(f'❌ File validation failed: {str(e)}')
            return False, f'Validation error: {str(e)}'

    def estimate_chunks(self, filepath: str) -> int:
        """
        Estimate number of chunks for a document
        
        Args:
            filepath: Path to document
        
        Returns:
            Estimated number of chunks
        """
        try:
            is_valid, _ = self.validate_file(filepath)
            if not is_valid:
                return 0
            
            # Get file extension
            file_ext = os.path.splitext(filepath)[1].lower()
            
            # Extract text
            if file_ext == '.pdf':
                text = self._extract_pdf(filepath)
            elif file_ext in ['.docx', '.doc']:
                text = self._extract_docx(filepath)
            elif file_ext == '.txt':
                text = self._extract_txt(filepath)
            else:
                return 0
            
            # Clean and estimate chunks
            text = self._clean_text(text)
            estimated = max(1, len(text) // self.chunk_size)
            
            logger.info(f'📊 Estimated chunks: {estimated}')
            
            return estimated
        
        except Exception as e:
            logger.error(f'❌ Chunk estimation failed: {str(e)}')
            return 0


# ============================================
# TESTING & DEBUGGING
# ============================================

if __name__ == '__main__':
    """Test document processor"""
    
    logging.basicConfig(level=logging.DEBUG)
    
    print('\n🚀 Testing Document Processor...\n')
    
    try:
        processor = DocumentProcessor()
        print('✅ Document Processor initialized\n')
        
        # Test with a sample text file
        test_file = 'sample.txt'
        
        if os.path.exists(test_file):
            print(f'📄 Processing: {test_file}')
            chunks = processor.process_document(test_file)
            print(f'✅ Processed into {len(chunks)} chunks\n')
            
            # Print first chunk
            if chunks:
                print(f'📋 First chunk preview:')
                print(f'{chunks[0][:200]}...\n')
        else:
            print(f'⚠️  Test file not found: {test_file}\n')
        
        print('✅ Document Processor test completed\n')
    
    except Exception as e:
        print(f'\n❌ Test failed: {str(e)}\n')
        sys.exit(1)