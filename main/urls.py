from django.urls import path
from .views import *
from .views_progress import indexing_progress_view
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
    path('download_file?collection_id=<int:collection_id>&file_index=<int:file_index>/', collection_download_file, name='collection_download_file'),
    path('indexing-progress/', indexing_progress_view, name='indexing_progress'),
    # User management URLs
    path('users/', users_list, name='users_list'),
    path('users/create/', user_create, name='user_create'),
    path('users/edit/<str:username>/', user_edit, name='user_edit'),
    path('users/delete/<str:username>/', user_delete, name='user_delete'),
]