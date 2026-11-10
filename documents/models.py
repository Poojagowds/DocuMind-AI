from django.db import models

class PDFDocument(models.Model):
    title = models.CharField(max_length=200)
    pdf_file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_summarized = models.BooleanField(default=False)
    summary_text = models.TextField(blank=True)

    def __str__(self):
        return self.title
class ChatMessage(models.Model):
    document = models.ForeignKey(
        PDFDocument,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )

    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question[:50]