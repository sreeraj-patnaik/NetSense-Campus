from django.contrib import admin

# Register your models here.
# registering the models to be visible in the admin interface
from .models import Block, Floor
admin.site.register(Block)
admin.site.register(Floor)

