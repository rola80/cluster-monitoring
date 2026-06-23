"""구비서류 수집: (중첩) zip 해제 후 PDF 목록화."""
import os, zipfile, tempfile, shutil

try:
    import pyzipper  # AES 암호화 zip 대응(선택)
except Exception:
    pyzipper = None


def _open_zip(path, pw):
    if pyzipper is not None:
        try:
            zf = pyzipper.AESZipFile(path)
            if pw:
                zf.setpassword(pw.encode())
            return zf
        except Exception:
            pass
    zf = zipfile.ZipFile(path)
    if pw:
        zf.setpassword(pw.encode())
    return zf


def extract_all(src_path, workdir=None, pw=""):
    """zip(중첩 포함) 또는 폴더를 받아 PDF 경로 리스트를 반환."""
    workdir = workdir or tempfile.mkdtemp(prefix="cluster_")
    pdfs = []

    def walk_zip(zpath, dest):
        os.makedirs(dest, exist_ok=True)
        with _open_zip(zpath, pw) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                try:
                    data = zf.read(info)
                except RuntimeError:
                    raise RuntimeError(f"비밀번호 오류 또는 미지정: {os.path.basename(zpath)}")
                out = os.path.join(dest, os.path.basename(info.filename))
                with open(out, "wb") as f:
                    f.write(data)
                low = out.lower()
                if low.endswith(".zip"):
                    walk_zip(out, out + "_x")
                elif low.endswith(".pdf"):
                    pdfs.append(out)

    if os.path.isdir(src_path):
        for root, _, files in os.walk(src_path):
            for fn in files:
                p = os.path.join(root, fn)
                if fn.lower().endswith(".zip"):
                    walk_zip(p, p + "_x")
                elif fn.lower().endswith(".pdf"):
                    pdfs.append(p)
    elif src_path.lower().endswith(".zip"):
        walk_zip(src_path, workdir)
    elif src_path.lower().endswith(".pdf"):
        pdfs.append(src_path)

    return sorted(set(pdfs))
