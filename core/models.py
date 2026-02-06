from django.db import models

# Create your models here.
class Block(models.Model):
    name = models.CharField(max_length=50)

class Floor(models.Model):
    block = models.ForeignKey(Block, on_delete=models.CASCADE)
    floor_number = models.IntegerField()
    name = models.CharField(max_length=50)

    map_image = models.ImageField(upload_to="floors/")
    rows = models.IntegerField()
    cols = models.IntegerField()

    blocked_cells = models.JSONField(default=list)