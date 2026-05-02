"""CUDA driver-mount setup for Modal GPU containers.

Modal mounts the host's NVIDIA driver libs at runtime, but the mount
layout is brittle:
  - Driver libs land at /usr/lib/x86_64-linux-gnu/libcuda.so.<version>
  - The SONAME paths (libcuda.so, libcuda.so.1) exist as 0-byte stubs
    alongside the real driver. dlopen("libcuda.so.1") finds the stub
    first → torch.cuda.is_available() returns False.
  - /usr/local/cuda*/compat ships forward-compat libs at version
    560.35.05. Modal's actual driver is 580.95.05. If compat is on
    LD_LIBRARY_PATH first, libcuda.so.580 dlopens libnvidia-
    ptxjitcompiler.so.560 — 20-major-version ABI mismatch → SIGSEGV
    on the first JIT-compiled kernel.

This module fixes both: replaces 0-byte stubs with proper symlinks
to the real versioned libs, and builds an LD_LIBRARY_PATH that
excludes the compat dirs entirely. Idempotent — kept symlinks
return immediately, so calling on every container invocation is
cheap.

Used by the rife_normalize_remote GPU function. Was previously
inlined in handler.py at module-startup, but handler.py runs on
the CPU-only orchestrator now (no GPU there to fix), so the logic
moved here where it belongs.
"""
import os
import subprocess


def setup_cuda_driver_mount():
    """Fix the libcuda.so SONAME mount + LD_LIBRARY_PATH for the GPU container.

    Run at the top of every GPU function invocation. Safe to call
    repeatedly — symlinks already pointing at real libs are kept;
    LD_LIBRARY_PATH is rebuilt cleanly each time.
    """
    try:
        _smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if _smi.returncode == 0:
            print(f"[cuda-setup] GPU: {_smi.stdout.strip()}", flush=True)
        else:
            print(f"[cuda-setup] nvidia-smi failed: {_smi.stderr.strip()[:200]}", flush=True)

        # Remove CUDA stub/compat libs that intercept dlopen before Modal's real
        # drivers. The CUDA 12.6 base image ships libcuda.so.560.x in
        # /usr/local/cuda — must be removed so FFmpeg picks up the real Modal-
        # mounted driver (580.x) from /usr/lib/x86_64-linux-gnu/.
        for _stub_dir in ["/usr/local/cuda/lib64/stubs",
                          "/usr/local/cuda/targets/x86_64-linux/lib/stubs",
                          "/usr/local/cuda/compat"]:
            if os.path.isdir(_stub_dir):
                for _sf in os.listdir(_stub_dir):
                    if "encode" in _sf.lower() or "cuda.so" in _sf.lower():
                        try:
                            os.remove(os.path.join(_stub_dir, _sf))
                        except Exception:
                            pass
        for _cuda_dir in ["/usr/local/cuda/lib64", "/usr/local/cuda/targets/x86_64-linux/lib"]:
            if os.path.isdir(_cuda_dir):
                for _sf in os.listdir(_cuda_dir):
                    if _sf.startswith("libcuda.so"):
                        try:
                            os.remove(os.path.join(_cuda_dir, _sf))
                        except Exception:
                            pass

        # Modal mounts the NVIDIA driver libs into /usr/lib/x86_64-linux-gnu/.
        # Older mount path /usr/local/nvidia/lib* is kept as a defensive
        # include for the legacy Modal scheme.
        #
        # CRITICAL: do NOT include /usr/local/cuda*/compat in the search path.
        # Those dirs ship CUDA forward-compat libs at version 560.35.05.
        # With Modal's NEW driver (580.95.05) bind-mounted into
        # /usr/lib/x86_64-linux-gnu/, putting compat first made libcuda.so.580
        # dlopen libnvidia-ptxjitcompiler.so.560 — 20-major-version ABI
        # mismatch that segfaulted on the first JIT-compiled kernel.
        _nvidia_lib_dirs = []
        for _search_dir in ["/usr/local/nvidia/lib", "/usr/local/nvidia/lib64",
                            "/usr/lib/x86_64-linux-gnu", "/usr/lib64",
                            "/usr/local/cuda/lib64"]:
            if os.path.isdir(_search_dir):
                _nvidia_lib_dirs.append(_search_dir)
        if _nvidia_lib_dirs:
            _existing_ldpath = os.environ.get("LD_LIBRARY_PATH", "")
            os.environ["LD_LIBRARY_PATH"] = (
                ":".join(_nvidia_lib_dirs)
                + (":" + _existing_ldpath if _existing_ldpath else "")
            )
            print(f"[cuda-setup] LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH'][:200]}", flush=True)

        def _ensure_soname_symlink(sym_path, target_name, lib_dir):
            """Make `sym_path` a symlink to `lib_dir/target_name`.
            If sym_path is a working symlink already pointing at a real
            file, leave it. If it's an empty stub or broken symlink,
            replace it. Returns (action, msg) for logging."""
            target_abs = os.path.join(lib_dir, target_name)
            try:
                existing_size = os.path.getsize(sym_path)  # follows symlinks
            except OSError:
                existing_size = -1
            if existing_size > 1024:
                return ("kept", f"{sym_path} → existing ({existing_size}B)")
            try:
                if os.path.lexists(sym_path):
                    os.unlink(sym_path)
                os.symlink(target_abs, sym_path)
                return ("linked", f"{sym_path} → {target_abs}")
            except Exception as _e:
                return ("failed", f"{sym_path}: {_e}")

        _symlink_log = []
        for _lib_dir in _nvidia_lib_dirs:
            try:
                _entries = os.listdir(_lib_dir)
            except OSError:
                continue

            # libnvidia-* sonames: find the real versioned file (>1KB) and
            # ensure libnvidia-<base>.so + .so.1 symlinks point at it.
            _libnvidia_real = {}
            for _f in _entries:
                if (
                    _f.startswith("libnvidia-")
                    and ".so." in _f
                    and not _f.endswith(".so.1")
                    and not _f.endswith(".so.0")
                ):
                    _full = os.path.join(_lib_dir, _f)
                    try:
                        if os.path.getsize(_full) > 1024:
                            _base = _f.split(".so.")[0]
                            _libnvidia_real.setdefault(_base, _f)
                    except OSError:
                        pass
            for _base, _real_f in _libnvidia_real.items():
                for _suf in [".so.1", ".so"]:
                    _sym = os.path.join(_lib_dir, f"{_base}{_suf}")
                    _action, _msg = _ensure_soname_symlink(_sym, _real_f, _lib_dir)
                    if _action != "kept":
                        _symlink_log.append(_msg)

            # libcuda.so + libcuda.so.1: same logic — find the real
            # libcuda.so.<version> file and ensure both sonames symlink to it.
            _libcuda_real = None
            for _f in _entries:
                if _f.startswith("libcuda.so.") and not _f.endswith(".so.1") and not _f.endswith(".so.0"):
                    _full = os.path.join(_lib_dir, _f)
                    try:
                        if os.path.getsize(_full) > 1024:
                            _libcuda_real = _f
                            break
                    except OSError:
                        pass
            if _libcuda_real:
                for _sym_name in ["libcuda.so.1", "libcuda.so"]:
                    _sym = os.path.join(_lib_dir, _sym_name)
                    _action, _msg = _ensure_soname_symlink(_sym, _libcuda_real, _lib_dir)
                    if _action != "kept":
                        _symlink_log.append(_msg)

        if _symlink_log:
            for _msg in _symlink_log:
                print(f"[cuda-setup] symlink: {_msg}", flush=True)
        subprocess.run(["ldconfig"], capture_output=True, timeout=5)

        # Diagnostic AFTER symlink fix + ldconfig: list every libcuda* and
        # libnvidia-* in the real driver dirs AND in the compat dirs we
        # excluded from LD_LIBRARY_PATH. The compat-dir scan stays in so a
        # future driver-mount mismatch is visible at a glance: if compat
        # shows version X and real-driver dir shows version Y and X != Y,
        # we know we're back in segfault-prone territory.
        _diag_dirs = list(_nvidia_lib_dirs)
        for _d in ["/usr/local/cuda/compat", "/usr/local/cuda-12.6/compat"]:
            if os.path.isdir(_d) and _d not in _diag_dirs:
                _diag_dirs.append(_d)
        for _d in _diag_dirs:
            try:
                _hits = []
                for _f in sorted(os.listdir(_d)):
                    if _f.startswith("libcuda.so") or _f.startswith("libnvidia-"):
                        _full = os.path.join(_d, _f)
                        try:
                            _size = os.path.getsize(_full)
                        except OSError:
                            _size = -1
                        _link = ""
                        if os.path.islink(_full):
                            try:
                                _link = f"->{os.readlink(_full)}"
                            except OSError:
                                pass
                        _hits.append(f"{_f}({_size}B){_link}")
                if _hits:
                    print(f"[cuda-setup] nvlibs in {_d}: {_hits}", flush=True)
            except OSError:
                pass
    except Exception as _e:
        print(f"[cuda-setup] failed: {_e}", flush=True)
