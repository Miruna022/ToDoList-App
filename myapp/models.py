from django.db import models

# Creyour models here.
class Event(models.Model):
    title = models.CharField(max_length = 100)
    description = models.TextField(blank = True)
    start = models.DateTimeField()
    end = models.DateTimeField()