from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path(
        'summary/<int:document_id>/',
        views.view_summary,
        name='view_summary'
    ),

    path(
        'download-summary/<int:document_id>/',
        views.download_summary,
        name='download_summary'
    ),

    path(
        'chat/<int:document_id>/',
        views.chat_with_pdf,
        name='chat_with_pdf'
    ),

    path(
        'delete/<int:document_id>/',
        views.delete_document,
        name='delete_document'
    ),

    path(
        'open-selected-chat/',
        views.open_selected_chat,
        name='open_selected_chat'
    ),

    path(
    'clear-chat/<int:document_id>/',
    views.clear_chat,
    name='clear_chat'
),
]