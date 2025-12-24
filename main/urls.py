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
    path('delete_thread?thread_id=<int:thread_id>/', delete_view, name='delete_thread'),
    path('collections/', collections_view, name='main_collection'),
    path('collections/<int:collection_id>/', collections_view, name='collection'),
    path('create_collection', collection_create_view, name='create_collection'),
    path('Add_docs?collection_id=<int:collection_id>/', collection_add_docs_view, name='collection_add_docs'),
    path('reindex_collection?collection_id=<int:collection_id>/', collection_reindex_view, name='reindex_collection'),
    path('delete_collection?collection_id=<int:collection_id>/', collection_delete_view, name='delete_collection'),
]