"I:\Programming\PythonDev\Python310\PrepareLoraKit\.venv\lib\site-packages\bitsandbytes\cextension.py", line 269, in throw_on_call
    raise RuntimeError(f"{self.formatted_error}Native code method attempted to call: lib.{name}()")
RuntimeError:
🚨 CUDA VERSION MISMATCH 🚨
Requested CUDA version:          13.2
Detected PyTorch CUDA version:   13.2
Available pre-compiled versions:
  - 11.8
  - 12.0
  - 12.1
  - 12.2
  - 12.3
  - 12.4
  - 12.5
  - 12.6
  - 12.8
  - 12.9
  - 13.0
This means:
The version you're trying to use is NOT distributed with this package
Attempted to use bitsandbytes native library functionality but it's not available.
This typically happens when:
1. bitsandbytes doesn't ship with a pre-compiled binary for your CUDA version
2. The library wasn't compiled properly during installation from source
To make bitsandbytes work, the compiled library version MUST exactly match the linked CUDA version.
If your CUDA version doesn't have a pre-compiled binary, you MUST compile from source.
You have two options:
1. COMPILE FROM SOURCE (required if no binary exists):
   https://huggingface.co/docs/bitsandbytes/main/en/installation#cuda-compile
2. Use BNB_CUDA_VERSION to specify a DIFFERENT CUDA version from the detected one, which is installed on your machine and matching an available pre-compiled version listed above
Original error: Configured CUDA binary not found at I:\Programming\PythonDev\Python310\PrepareLoraKit\.venv\lib\site-packages\bitsandbytes\libbitsandbytes_cuda132.dll
🔍 Run this command for detailed diagnostics:
python -m bitsandbytes
If you've tried everything and still have issues:
1. Include ALL version info (operating system, bitsandbytes, pytorch, cuda, python)
2. Describe what you've tried in detail
3. Open an issue with this information:
   https://github.com/bitsandbytes-foundation/bitsandbytes/issues
Native code method attempted to call: lib.cint8_vector_quant()
🚨 CUDA VERSION MISMATCH 🚨