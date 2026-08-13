from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()


class PDFBuilder:

    def __init__(self, title):

        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(self.buffer)
        self.story = []

        self.story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
        self.story.append(Spacer(1, 20))

    def heading(self, text):

        self.story.append(Paragraph(text, styles["Heading2"]))
        self.story.append(Spacer(1, 10))

    def paragraph(self, text):

        self.story.append(Paragraph(str(text), styles["BodyText"]))
        self.story.append(Spacer(1, 6))

    def build(self):

        self.doc.build(self.story)

        pdf = self.buffer.getvalue()

        self.buffer.close()

        return pdf