"""
Document loading subprocess - isolated from Django to work with multiprocessing on Windows
"""
import sys
import os
import traceback
import pickle


def load_document_subprocess(file_path, result_file):
    """
    Load document in separate process and save to temp file.
    This function must be in a separate module to avoid Django import issues on Windows.
    """
    try:
        # Import here to avoid loading Django in subprocess
        from llama_index.core import SimpleDirectoryReader
        
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        ext = os.path.splitext(file_path)[1].lower()
        
        print(f"[SUBPROCESS] File: {os.path.basename(file_path)}", file=sys.stderr)
        print(f"[SUBPROCESS] Size: {file_size:.2f} MB, Type: {ext}", file=sys.stderr)
        print(f"[SUBPROCESS] Creating SimpleDirectoryReader...", file=sys.stderr)
        
        reader = SimpleDirectoryReader(
            input_files=[file_path],
            filename_as_id=True
        )
        
        print(f"[SUBPROCESS] Reader created, calling load_data()...", file=sys.stderr)
        docs = reader.load_data()
        
        print(f"[SUBPROCESS] ✓ Loaded {len(docs)} document chunks", file=sys.stderr)
        
        # Save to temporary file instead of queue (avoids serialization issues)
        print(f"[SUBPROCESS] Saving results to temp file...", file=sys.stderr)
        with open(result_file, 'wb') as f:
            pickle.dump(('success', docs), f)
        print(f"[SUBPROCESS] ✓ Results saved successfully", file=sys.stderr)
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[SUBPROCESS] ✗ Exception: {error_trace}", file=sys.stderr)
        try:
            with open(result_file, 'wb') as f:
                pickle.dump(('error', f"{type(e).__name__}: {str(e)}\n{error_trace}"), f)
        except:
            pass  # If we can't even save the error, subprocess will just exit
