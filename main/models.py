from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


class Document(models.Model):
    user =         models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    name =         models.CharField(max_length=256)
    loc =          models.CharField(max_length=512)
    public =       models.BooleanField(default=False)
    description =  models.TextField(max_length=1024, null=True)
    time_created = models.DateTimeField(auto_now_add=True)
    sha256 =       models.CharField(max_length=64, default=None)


class Collection(models.Model):
    # Collection types
    COLLECTION_TYPE_DOCUMENT = 'document'
    COLLECTION_TYPE_DATABASE = 'database'
    COLLECTION_TYPE_EXCEL = 'excel'
    
    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_DOCUMENT, 'Document-based Collection'),
        (COLLECTION_TYPE_DATABASE, 'Database-backed Collection'),
        (COLLECTION_TYPE_EXCEL, 'Excel/CSV-backed Collection'),
    ]
    
    # Database types
    DB_TYPE_MYSQL = 'mysql'
    DB_TYPE_POSTGRESQL = 'postgresql'
    DB_TYPE_SQLITE = 'sqlite'
    DB_TYPE_MONGODB = 'mongodb'
    
    DB_TYPE_CHOICES = [
        (DB_TYPE_MYSQL, 'MySQL'),
        (DB_TYPE_POSTGRESQL, 'PostgreSQL'),
        (DB_TYPE_SQLITE, 'SQLite'),
        (DB_TYPE_MONGODB, 'MongoDB'),
    ]
    
    user_created =   models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    name =           models.CharField(max_length=128)
    docs =           models.ManyToManyField(Document, related_name='collections', blank=True)
    allowed_groups = models.ManyToManyField(Group, related_name='allowed_collections')
    description =    models.TextField(max_length=1024, null=True, blank=True)
    time_created  =  models.DateTimeField(auto_now_add=True) 
    loc  =           models.CharField(max_length=512)
    
    # New fields for database-backed collections
    collection_type = models.CharField(max_length=20, choices=COLLECTION_TYPE_CHOICES, default=COLLECTION_TYPE_DOCUMENT)
    db_type =         models.CharField(max_length=20, choices=DB_TYPE_CHOICES, null=True, blank=True)
    db_connection_string = models.TextField(null=True, blank=True)  # For connection string or file paths
    db_schema_analysis = models.TextField(null=True, blank=True)  # LLM-generated schema analysis
    db_extra_knowledge = models.TextField(null=True, blank=True)  # Supervisor-provided additional info
    excel_file_paths = models.JSONField(null=True, blank=True)  # For storing paths to excel/csv files


class Thread(models.Model):
    user =            models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    name =            models.CharField(max_length=32)
    docs =            models.ManyToManyField(Document, related_name='vector_dbs')
    loc  =            models.CharField(max_length=512)
    description =     models.TextField(max_length=1024, null=True)
    time_created  =   models.DateTimeField(auto_now_add=True)
    base_collection = models.ForeignKey(Collection, null=True, on_delete=models.SET_NULL)

    
class ChatMessage(models.Model):
    thread   =     models.ForeignKey(Thread, on_delete=models.CASCADE)
    user        =  models.ForeignKey(get_user_model(), verbose_name='sender', on_delete=models.CASCADE)
    rag_response = models.BooleanField(default=False)
    message     =  models.TextField()
    timestamp   =  models.DateTimeField(auto_now_add=True)
    source_nodes = models.JSONField(null=True, blank=True)