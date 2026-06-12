"""Compile LaTeX → PDF using Tectonic.

Tectonic is a single static binary; first run downloads needed packages and
caches them. We invoke it as a subprocess from a per-job temp dir, then move
the resulting PDF to backend/pdfs/{job_id}.pdf.

If TECTONIC_BIN is set in env, we use that path; otherwise we expect
`tectonic` on PATH (Docker image installs it; locally `brew install tectonic`).
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

PDFS_DIR = Path(os.getenv("PDFS_DIR", "/app/pdfs"))


class LatexCompileError(RuntimeError):
    def __init__(self, message: str, log_excerpt: str = ""):
        super().__init__(message)
        self.log_excerpt = log_excerpt


def _tectonic_bin() -> str:
    return os.getenv("TECTONIC_BIN") or shutil.which("tectonic") or "tectonic"


def compile_latex(latex_source: str, job_id: int, *, timeout: int = 120) -> Path:
    """Returns absolute path to the compiled PDF. Raises LatexCompileError on failure."""
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = PDFS_DIR / f"{job_id}.pdf"

    with tempfile.TemporaryDirectory(prefix=f"job{job_id}-") as tmp:
        tmp_path = Path(tmp)
        tex_file = tmp_path / "resume.tex"
        tex_file.write_text(latex_source, encoding="utf-8")

        cmd = [
            _tectonic_bin(),
            "--keep-logs",
            "--outdir", str(tmp_path),
            "--chatter", "minimal",
            str(tex_file),
        ]
        log.info("Compiling job %d → %s", job_id, out_pdf)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise LatexCompileError(
                f"tectonic binary not found (set TECTONIC_BIN or install tectonic). "
                f"Tried: {_tectonic_bin()}"
            )
        except subprocess.TimeoutExpired:
            raise LatexCompileError(f"tectonic timed out after {timeout}s")

        if proc.returncode != 0:
            log_file = tmp_path / "resume.log"
            log_text = log_file.read_text(errors="replace") if log_file.exists() else ""
            stderr_excerpt = (proc.stderr or "")[-2000:]
            log.error("Tectonic failed for job %d: stderr=%s", job_id, stderr_excerpt[:500])
            raise LatexCompileError(
                f"tectonic exit={proc.returncode}",
                log_excerpt=(stderr_excerpt + "\n--- resume.log ---\n" + log_text[-3000:]),
            )

        produced = tmp_path / "resume.pdf"
        if not produced.exists():
            raise LatexCompileError("tectonic returned 0 but no PDF produced")
        shutil.move(str(produced), out_pdf)

    return out_pdf
