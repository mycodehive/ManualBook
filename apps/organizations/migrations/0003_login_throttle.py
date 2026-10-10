from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[('organizations','0002_legacy')]
    operations=[migrations.CreateModel(name='LoginThrottle',fields=[('key',models.CharField(max_length=64,primary_key=True,serialize=False)),('failures',models.PositiveIntegerField(default=0)),('window_started',models.DateTimeField()),('locked_until',models.DateTimeField(blank=True,null=True))])]
