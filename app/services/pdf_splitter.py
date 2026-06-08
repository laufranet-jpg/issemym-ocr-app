from pathlib import Path
from pypdf import PdfReader, PdfWriter

def split_pdf(input_pdf: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(input_pdf))
    generated_files = []

    for idx, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        output_path = output_dir / f"pagina_{idx:04d}.pdf"
        with open(output_path, "wb") as f:
            writer.write(f)
        generated_files.append(output_path)

    return generated_files
