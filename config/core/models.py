from django.db import models

# Create your models here.
class Block(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name
    
class Floor(models.Model):
    block = models.ForeignKey(Block, on_delete = models.CASCADE)
    number = models.IntegerField()
    
    image = models.ImageField(upload_to='floor_images/', null=True, blank=True)

    rows = models.IntegerField(null=True, blank=True)
    cols = models.IntegerField(null=True, blank=True)
    blocked_cells = models.JSONField(default=list)  # List of blocked cell coordinates

    def __str__(self):
        return f"{self.block.name} - Floor {self.number}"
    def total_cells(self):
        if self.rows and self.cols:
            return self.rows * self.cols
        return 0
    

