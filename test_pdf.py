
import fitz

pdf = fitz.open("sample.pdf")

for page_number, page in enumerate(pdf, start=1):
    text = page.get_text()

    print("Page:", page_number)
    print(text)

pdf.close()
