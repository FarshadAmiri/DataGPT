from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


class Document(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    loc =  models.CharField(max_length=512)
    public = models.BooleanField(default=False)
    description = models.TextField(max_length=1024, null=True)
    time_created   =  models.DateTimeField(auto_now_add=True)


class Thread(models.Model):
    user =   models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    name =   models.CharField(max_length=32)
    docs =   models.ManyToManyField(Document, related_name='vector_dbs')
    loc  =   models.CharField(max_length=512)
    public = models.BooleanField(default=False)
    description = models.TextField(max_length=1024, null=True)
    time_created   =  models.DateTimeField(auto_now_add=True)


class ChatMessage(models.Model):
    thread   =  models.ForeignKey(Thread, on_delete=models.CASCADE)
    user        =  models.ForeignKey(get_user_model(), verbose_name='sender', on_delete=models.CASCADE)
    rag_response = models.BooleanField(default=False)
    message     =  models.TextField()
    timestamp   =  models.DateTimeField(auto_now_add=True)


class Collection(models.Model):
    user_created =   models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    name =   models.CharField(max_length=128)
    docs =   models.ManyToManyField(Document, related_name='collections')
    allowed_groups = models.ManyToManyField(Group, related_name='allowed_collections')
    description = models.TextField(max_length=1024, null=True)
    time_created   =  models.DateTimeField(auto_now_add=True)