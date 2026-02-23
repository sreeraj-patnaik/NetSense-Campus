from django.db import models

# Create your models here.
class Block(models.Model):
    name = models.Charfield(max_length=100)
    
    def __str__(self):
        return self.name
    
class Floor(models.Model):
    block = models.ForeignKey(Block, on_delete = models.CASCADE)
    number = models.IntegerField()
    
    image = models.ImageField(upload_to='floor_images/')

    rows = models.IntegerField()
    cols = models.IntegerField()

    blocked_cells = models.JSONField(default=list)  # List of blocked cell coordinates

    def __str__(self):
        return f"{self.block.name} - Floor {self.number}"
    def total_cells(self):
        return self.rows * self.cols
    

