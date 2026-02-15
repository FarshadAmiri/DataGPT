#!/usr/bin/env python
"""
Test PDF loading to diagnose issues
Usage: python test_pdf_loading.py <path_to_pdf>
"""

import sys
import os
import time

def test_pdf(pdf_path):
    """Test loading a PDF file with various methods"""
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return
    
    file_size = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"Testing PDF: {os.path.basename(pdf_path)}")
    print(f"Size: {file_size:.2f} MB")
    print(f"{'='*60}\n")
    
    # Test 0: Check system PDF tools
    print("0. Checking system PDF utilities...")
    import subprocess
    try:
        result = subprocess.run(['pdfinfo', pdf_path], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.split('\n')[:5]
            print(f"   ✓ pdfinfo works:")
            for line in lines:
                if line.strip():
                    print(f"      {line}")
        else:
            print(f"   ✗ pdfinfo failed: {result.stderr[:100]}")
    except FileNotFoundError:
        print(f"   ✗ pdfinfo not installed (install poppler-utils)")
    except subprocess.TimeoutExpired:
        print(f"   ⚠ pdfinfo timed out")
    except Exception as e:
        print(f"   ✗ pdfinfo error: {e}")
    
    # Test 1: Check available libraries
    print("1. Checking PDF libraries...")
    libs_found = []
    
    try:
        import PyPDF2
        print(f"   ✓ PyPDF2 v{PyPDF2.__version__}")
        libs_found.append('PyPDF2')
    except ImportError:
        print(f"   ✗ PyPDF2 not installed")
    
    try:
        import fitz  # PyMuPDF
        print(f"   ✓ PyMuPDF v{fitz.__version__}")
        libs_found.append('PyMuPDF')
    except ImportError:
        print(f"   ✗ PyMuPDF not installed")
    
    try:
        import pdfminer
        print(f"   ✓ pdfminer v{pdfminer.__version__}")
        libs_found.append('pdfminer')
    except ImportError:
        print(f"   ✗ pdfminer not installed")
    
    if not libs_found:
        print("\n❌ No PDF libraries found! Install at least one:")
        print("   pip install PyMuPDF  # Recommended")
        return
    
    # Test 2: LlamaIndex SimpleDirectoryReader
    print("\n2. Testing LlamaIndex SimpleDirectoryReader...")
    try:
        from llama_index.core import SimpleDirectoryReader
        
        print(f"   Creating reader...")
        start = time.time()
        reader = SimpleDirectoryReader(input_files=[pdf_path], filename_as_id=True)
        print(f"   ✓ Reader created ({time.time()-start:.2f}s)")
        
        print(f"   Loading document...")
        start = time.time()
        docs = reader.load_data()
        elapsed = time.time() - start
        
        print(f"   ✓ SUCCESS!")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Chunks: {len(docs)}")
        if docs:
            print(f"   First chunk length: {len(docs[0].text)} chars")
        
    except Exception as e:
        print(f"   ✗ FAILED: {type(e).__name__}: {e}")
        import traceback
        print(f"\n   Traceback:")
        traceback.print_exc()
    
    # Test 3: Direct PyMuPDF test (if available)
    if 'PyMuPDF' in libs_found:
        print("\n3. Testing direct PyMuPDF access...")
        try:
            import fitz
            start = time.time()
            doc = fitz.open(pdf_path)
            print(f"   ✓ Opened PDF ({time.time()-start:.2f}s)")
            print(f"   Pages: {len(doc)}")
            
            if len(doc) > 0:
                print(f"   Extracting text from first page...")
                start = time.time()
                text = doc[0].get_text()
                print(f"   ✓ Extracted ({time.time()-start:.2f}s)")
                print(f"   Text length: {len(text)} chars")
            
            doc.close()
            
        except Exception as e:
            print(f"   ✗ FAILED: {type(e).__name__}: {e}")
    
    print(f"\n{'='*60}")
    print("Testing complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_loading.py <path_to_pdf>")
        print("\nExample:")
        print("  python test_pdf_loading.py /path/to/document.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    test_pdf(pdf_path)
