from django.urls import path
from .views import *
from rest_framework.authtoken.views import obtain_auth_token
from .views import *

app_name = 'main'

urlpatterns = [
    path('', chat_view, name='main_chat'),
    path('<int:thread_id>/', chat_view, name='chat'),
    path('create_rag', create_rag_view, name='create_rag'),
    path('Add_docs?thread_id=<int:thread_id>/', add_docs_view, name='add_docs'),
    path("test", testView, name='test'),
]