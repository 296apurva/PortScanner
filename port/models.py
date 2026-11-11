from django.db import models

class ScanHistory(models.Model):
    target_ip = models.CharField(max_length=100)
    scanned_at = models.DateTimeField(auto_now_add=True)
    open_ports_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.target_ip} — {self.scanned_at}"

class PortResult(models.Model):
    scan = models.ForeignKey(ScanHistory, on_delete=models.CASCADE, related_name='results')
    port = models.IntegerField()
    service = models.CharField(max_length=100, default='unknown')
    banner = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Port {self.port} ({self.service})"