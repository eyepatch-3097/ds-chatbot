from django.urls import path
from .views import chat_message, submit_lead, chat_stats, chatbot_dashboard, lead_list

urlpatterns = [
    path('message/', chat_message, name='chat_message'),
    path('lead/', submit_lead, name='submit_lead'),
    path('stats/', chat_stats, name='chat_stats'),
    path('dashboard/', chatbot_dashboard, name='chatbot_dashboard'),
    path('leads-view/', lead_list, name='chat_lead_list'),
]
