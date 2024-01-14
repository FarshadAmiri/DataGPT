from django.urls import path
from .views import *
from rest_framework.authtoken.views import obtain_auth_token
from .views import *

app_name = 'main'

urlpatterns = [
    path('', chat_view, name='main_chat'),
    path('<chat_id>/', chat_view, name='chat'),
    path('create_rag', create_rag_view, name='create_rag'),
    path("test", testView, name='test'),
]